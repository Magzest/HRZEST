resource "aws_s3_bucket" "hrms_storage" {
  bucket = "${var.project_name}-storage-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-storage"
  }
}

resource "aws_s3_bucket_public_access_block" "hrms_storage_pab" {
  bucket                  = aws_s3_bucket.hrms_storage.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "hrms_storage_lifecycle" {
  bucket = aws_s3_bucket.hrms_storage.id

  rule {
    id     = "purge-garbage"
    status = "Enabled"
    filter {
      prefix = "garbage/"
    }
    expiration {
      days = 30
    }
  }

  rule {
    id     = "purge-cache"
    status = "Enabled"
    filter {
      prefix = "cache/"
    }
    expiration {
      days = 30
    }
  }
}

# ── Database backups (offsite, versioned) ────────────────────────────────────
# Separate from hrms_storage above deliberately: that bucket's two lifecycle
# rules purge everything in it after 30 days by design (ephemeral cache/
# garbage), which is the wrong retention policy for something you may need
# to restore from months later. scripts/backup_db.sh uploads here after
# every local pg_dump -- see RESTORE.md for the restore procedure.
resource "aws_s3_bucket" "backups" {
  bucket = "${var.project_name}-backups-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-backups"
  }
}

resource "aws_s3_bucket_public_access_block" "hrms_backups_pab" {
  bucket                  = aws_s3_bucket.backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Versioning means an accidental overwrite/delete of a same-named backup
# object doesn't destroy the prior version -- backup_db.sh's filenames are
# already timestamped so this mostly guards against out-of-band deletes
# (a compromised or fat-fingered `aws s3 rm`) rather than same-key
# overwrites, but it's the property item #8 of the audit specifically
# asked for.
resource "aws_s3_bucket_versioning" "hrms_backups_versioning" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "hrms_backups_sse" {
  bucket = aws_s3_bucket.backups.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "hrms_backups_lifecycle" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    filter {
      prefix = ""
    }
    # Current (latest) version of every backup object is kept forever --
    # this only cleans up NONCURRENT versions (superseded by a later
    # upload to the same key, or removed out-of-band) after 90 days, so
    # versioning above doesn't grow storage costs unbounded.
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}
