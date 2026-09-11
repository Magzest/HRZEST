# Database backup & restore

This is the disaster-recovery procedure for HRzest.com's PostgreSQL database.
If you're reading this because production is down, skip to
[**Restore procedure**](#restore-procedure).

## How backups work

- `scripts/backup_db.sh` runs `pg_dump | gzip`, writes a timestamped copy to
  `backups/` on the app server, and uploads it to the `backups` S3 bucket
  (`terraform/s3_storage.tf`) if `BACKUP_S3_BUCKET` is set (see
  `.env.example`). The S3 copy is the durable one — the local copy alone
  does not survive losing the host it's on.
- Scheduled daily at 02:15 server time via `scripts/hrzest-backup.service`
  + `scripts/hrzest-backup.timer` (systemd). Local copies older than 30
  days are pruned automatically; S3 keeps every backup's current version
  forever and expires only superseded/deleted *versions* after 90 days
  (`terraform/s3_storage.tf`'s `hrms_backups_lifecycle` rule) — versioning
  is enabled specifically so an accidental `aws s3 rm` doesn't destroy a
  backup outright.
- `BACKUP_HEARTBEAT_URL` (optional, `.env.example`) pings a dead-man's-switch
  monitor (Healthchecks.io, Cronitor, etc.) on every successful run — set
  this up so a silently-broken backup job is discovered by an alert, not by
  needing a backup that turns out not to exist.

## One-time setup (new deployment)

1. Apply the `backups` S3 bucket: `terraform apply` picks it up automatically
   from `terraform/s3_storage.tf` once the rest of the terraform config is
   applied. **Known gap as of this writing:** several *other* resources this
   terraform config's `outputs.tf` already references —
   `aws_iam_instance_profile.ec2_app_profile`, `aws_security_group.app_firewall`,
   `aws_sns_topic.alerts`, `aws_db_instance.this` — are not actually defined
   anywhere in `terraform/*.tf`, so a bare `terraform apply` will fail with
   "reference to undeclared resource" until those are added or the outputs
   referencing them are removed. This is a pre-existing gap unrelated to
   backups specifically; the `backups` bucket itself has no such issue.
2. Grant the EC2 instance's IAM role `s3:PutObject` on
   `arn:aws:s3:::<project>-backups-<account-id>/*` (once
   `ec2_app_profile` above exists) — the backup script relies on the AWS
   CLI's normal credential chain, so no static keys need to touch the host.
   Until that role exists, either provision the bucket manually or run the
   script with `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` set (fine for a
   one-off, not recommended long-term).
3. Set `BACKUP_S3_BUCKET=<project>-backups-<account-id>` in `.env` on the
   app server.
4. Install the scheduled job:
   ```bash
   sudo cp scripts/hrzest-backup.service scripts/hrzest-backup.timer /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now hrzest-backup.timer
   systemctl list-timers hrzest-backup.timer   # confirm it's scheduled
   ```
5. Trigger one backup immediately rather than waiting for 02:15, to confirm
   the whole chain (dump → gzip → S3 upload → heartbeat) actually works on
   this host:
   ```bash
   sudo systemctl start hrzest-backup.service
   journalctl -u hrzest-backup.service -n 50 --no-pager
   aws s3 ls "s3://$BACKUP_S3_BUCKET/backups/" | tail -5
   ```

## Restore procedure

**Read this whole section before running anything against production.**
Restoring into an already-populated database will fail on the first
`CREATE TABLE` (tables already exist) rather than silently merging or
overwriting — that's expected. Restore into a **new, empty database** and
cut the app over to it, don't restore on top of a live one.

1. **Get the backup file.**
   ```bash
   # From S3 (the durable copy) — list and pick the one you need:
   aws s3 ls "s3://$BACKUP_S3_BUCKET/backups/"
   aws s3 cp "s3://$BACKUP_S3_BUCKET/backups/db_backup_2026-01-15_02-15-03.sql.gz" .

   # Or from the app server's local copy, if it's still there and recent:
   ls -la /opt/employee-attendance/backups/
   ```

2. **Create a fresh, empty target database.** Never restore over the
   database the app is currently pointed at.
   ```bash
   psql -h <DB_HOST> -U <DB_USER> -d postgres \
     -c "CREATE DATABASE employee_attendance_restored;"
   ```

3. **Restore.**
   ```bash
   gunzip -c db_backup_2026-01-15_02-15-03.sql.gz \
     | psql -h <DB_HOST> -U <DB_USER> -d employee_attendance_restored
   ```
   Expect a stream of `SET`/`CREATE TABLE`/`ALTER TABLE`/`COPY N` lines
   ending without an error. A `COPY 0` for a table you expected data in is
   a red flag — that table was empty at backup time, not a restore failure,
   but worth double-checking against what you expected.

4. **Spot-check the data landed correctly** before cutting anything over —
   pick 2-3 tables you know should have rows and confirm counts/recent
   timestamps look right:
   ```bash
   psql -h <DB_HOST> -U <DB_USER> -d employee_attendance_restored \
     -c "SELECT COUNT(*) FROM employees;" \
     -c "SELECT MAX(date) FROM attendance;"
   ```

5. **Cut the app over.** Update `DB_NAME` (and `DB_HOST` if restoring to a
   different server/RDS instance) in `.env` to point at the restored
   database, then restart the app (`podman-compose restart app` /
   `docker compose restart app`, matching whichever compose file this
   deployment uses). Confirm `/healthz` returns `{"status":"ok"}` before
   considering the restore complete.

6. **Don't delete the old (broken) database immediately** — keep it until
   you've confirmed the restored one is serving real traffic correctly for
   at least a few hours, in case the restore itself needs redoing.

### Restoring a single table (not the whole database)

`pg_dump`'s output is a plain SQL script, so you can restore into a scratch
database (steps 1-3 above, using a throwaway database name) and then copy
just the table(s) you need back into production with `pg_dump -t
<table_name> ... | psql ...` from the scratch database, or a manual
`INSERT INTO ... SELECT ... FROM dblink(...)` — there's no single-table
extraction flag for a plain-SQL dump; the scratch-database round trip is
the straightforward way.

## Verified

This procedure (steps 2-4 above, without the S3 fetch) was run end-to-end
against a local scratch database on 2026-09-11: a table with known rows was
created, backed up via `scripts/backup_db.sh` unmodified, restored into a
fresh database via the exact commands in step 3, and the restored rows were
confirmed to match byte-for-byte. The S3 upload/download steps use the
standard `aws s3 cp`/`aws s3 ls` commands directly and were not
independently re-verified here (no AWS credentials were available in the
environment this was written in) — verify those specifically the first
time this is set up for real, per step 5 of the one-time setup above.
