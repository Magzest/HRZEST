#!/bin/bash
# deploy.sh — Bootstrap employee-attendance on a fresh Ubuntu/Debian VPS
# Usage: curl -sSL <raw_url>/deploy.sh | bash
# Or:    chmod +x deploy.sh && sudo ./deploy.sh
#
# Runs the stack as rootless Podman under a dedicated unprivileged user —
# there is no root-owned container daemon/socket at all. Recommended target:
# Ubuntu 24.04 LTS (ships Podman 4.9); Ubuntu 22.04's stock Podman (3.4.4) is
# old enough that rootless behavior may differ from what's assumed here.
set -euo pipefail

REPO_URL="https://github.com/Nithin-magzest/emplyeee-attendance.git"
APP_DIR="/opt/employee-attendance"
APP_USER="attendance"

echo "==> Installing system packages"
apt-get update -q
apt-get install -y -q \
    git curl ca-certificates gnupg \
    podman podman-compose \
    ufw fail2ban unattended-upgrades openssl

# Podman is daemonless (no persistent background service to enable/start) —
# `podman-compose` invokes `podman` directly per command.

echo "==> Hardening: firewall (ufw)"
# No 'ufw --force reset' here — this script is meant to be safely re-run (see
# the .env placeholder check below), and a reset would silently wipe any
# custom rules an operator added between runs. allow/limit/default are all
# idempotent on their own, so just (re-)apply the baseline.
ufw default deny incoming
ufw default allow outgoing
ufw limit 22/tcp    # rate-limited SSH — slows down brute-force attempts

# nginx runs as an unprivileged user inside its container (nginx-unprivileged
# image, cap_drop: ALL — see compose.yaml) and can't bind ports <1024, so it
# only ever binds 8080/8443 on the host. Redirect the real public ports to
# those via a PREROUTING DNAT rule in ufw's own nat table (before.rules),
# rather than granting the container NET_BIND_SERVICE — keeps the container
# fully unprivileged while 80/443 still work transparently for browsers and
# Let's Encrypt's HTTP-01 validation (which always uses port 80).
#
# iptables' nat/PREROUTING runs before the filter table's INPUT chain, so by
# the time ufw's own filter rules evaluate a redirected packet, its
# destination port has ALREADY been rewritten to 8080/8443 — the filter
# rules below must open the REWRITTEN port, not the original 80/443, or
# ufw's default-deny-incoming policy drops every "redirected" packet anyway.
UFW_BEFORE_RULES="/etc/ufw/before.rules"
if ! grep -q "employee-attendance: 80/443 -> 8080/8443 redirect" "$UFW_BEFORE_RULES"; then
    { cat <<'EOF'
# employee-attendance: 80/443 -> 8080/8443 redirect (nginx is unprivileged,
# can't bind ports <1024 — see compose.yaml / nginx.conf.template)
*nat
:PREROUTING ACCEPT [0:0]
-A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080
-A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 8443
COMMIT
EOF
      cat "$UFW_BEFORE_RULES"
    } > /tmp/ufw-before.rules.new
    mv /tmp/ufw-before.rules.new "$UFW_BEFORE_RULES"
fi
ufw allow 8080/tcp
ufw allow 8443/tcp

# Honeypot ("system32_crypto_admin", compose.yaml + utils/honeypot.py) —
# deliberately opt-in via ENABLE_HONEYPOT=1, NOT on by default. Unlike the
# 80/443 redirect above (required for the app itself to be reachable at
# all), opening FTP/Telnet/SMTP/MSSQL/MySQL/RDP publicly is a genuine,
# optional increase in internet-facing attack surface — re-running this
# script on an already-deployed server must never silently open new public
# ports just because a newer version of the script knows how to.
if [ "${ENABLE_HONEYPOT:-0}" = "1" ]; then
    echo "==> Honeypot enabled (ENABLE_HONEYPOT=1) — opening decoy ports 21/23/25/1433/3306/3389"
    if ! grep -q "employee-attendance: honeypot redirect" "$UFW_BEFORE_RULES"; then
        { cat <<'EOF'
# employee-attendance: honeypot redirect (system32_crypto_admin —
# utils/honeypot.py — runs unprivileged, can't bind ports <1024)
*nat
:PREROUTING ACCEPT [0:0]
-A PREROUTING -p tcp --dport 21 -j REDIRECT --to-port 8021
-A PREROUTING -p tcp --dport 23 -j REDIRECT --to-port 8023
-A PREROUTING -p tcp --dport 25 -j REDIRECT --to-port 8025
COMMIT
EOF
          cat "$UFW_BEFORE_RULES"
        } > /tmp/ufw-before.rules.new
        mv /tmp/ufw-before.rules.new "$UFW_BEFORE_RULES"
    fi
    # 8021/8023/8025 are the rewritten ports the filter table actually sees
    # (same reasoning as 8080/8443 above); 1433/3306/3389 are unprivileged
    # already so no redirect — but the security group also has to open
    # these publicly (see terraform/honeypot.tf, itself opt-in) or nothing
    # ever reaches this far regardless of what ufw allows.
    ufw allow 8021/tcp
    ufw allow 8023/tcp
    ufw allow 8025/tcp
    ufw allow 1433/tcp
    ufw allow 3306/tcp
    ufw allow 3389/tcp
fi

ufw --force enable
ufw reload

echo "==> Hardening: fail2ban (SSH brute-force protection)"
systemctl enable --now fail2ban

echo "==> Hardening: automatic OS security patches"
dpkg-reconfigure -f noninteractive unattended-upgrades || true
systemctl enable --now unattended-upgrades

echo "==> Hardening: SSH key-only auth"
# Ubuntu cloud images load /etc/ssh/sshd_config.d/*.conf (e.g. cloud-init's
# 50-cloud-init.conf, which sets PasswordAuthentication yes) via an Include
# near the top of sshd_config — and sshd uses the FIRST value it sees for
# each keyword, so editing only the main file below can silently lose to
# that drop-in. Write our own drop-in that sorts before it (00- prefix) so
# it wins, in addition to editing the main file for clarity/older OpenSSH.
mkdir -p /etc/ssh/sshd_config.d
echo "PasswordAuthentication no" > /etc/ssh/sshd_config.d/00-attendance-hardening.conf
if grep -q "^PasswordAuthentication" /etc/ssh/sshd_config; then
    sed -i 's/^PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
else
    echo "PasswordAuthentication no" >> /etc/ssh/sshd_config
fi
systemctl reload sshd || systemctl reload ssh || true
if command -v sshd >/dev/null && sshd -T 2>/dev/null | grep -qi "^passwordauthentication yes"; then
    echo "    WARNING: PasswordAuthentication is still enabled after hardening —"
    echo "    check /etc/ssh/sshd_config.d/ for a conflicting drop-in that loads"
    echo "    before 00-attendance-hardening.conf."
fi

echo "==> Creating app user and directory"
# Real shell (not nologin): CI's SSH deploy step logs in AS this user
# directly to run rootless podman-compose — nologin would refuse the SSH
# session entirely. It still has no sudo rights at all, which keeps this
# strictly less privileged than a shared root-owned daemon model would be.
id -u "$APP_USER" &>/dev/null || useradd -r -m -d "/home/$APP_USER" -s /bin/bash "$APP_USER"
mkdir -p "$APP_DIR"
chown "$APP_USER":"$APP_USER" "$APP_DIR"

# Rootless Podman remaps in-container UIDs onto a range of "subordinate" host
# UIDs it doesn't actually use directly. Regular users get one automatically
# via /etc/login.defs; system accounts (-r, used above) don't, so add one
# explicitly. Only needed once — re-running usermod --add-subuids on a range
# the user already has would error, so guard on /etc/subuid.
if ! grep -q "^$APP_USER:" /etc/subuid 2>/dev/null; then
    usermod --add-subuids 200000-265535 --add-subgids 200000-265535 "$APP_USER"
fi

# Let the app user's containers run without an active login session (so
# rootless podman-compose works non-interactively here) and start on boot
# instead of only on first login.
loginctl enable-linger "$APP_USER"
systemctl start "user@$(id -u "$APP_USER").service" 2>/dev/null || true

# Every podman/podman-compose call below runs as $APP_USER through this
# helper. Rootless Podman's storage and API socket live under that user's
# own $HOME/$XDG_RUNTIME_DIR — running podman directly as root here would
# create a second, entirely separate root-owned stack instead of managing
# this one.
APP_UID="$(id -u "$APP_USER")"
run_as_app() {
    runuser -u "$APP_USER" -- env "XDG_RUNTIME_DIR=/run/user/$APP_UID" "HOME=/home/$APP_USER" "$@"
}

# podman-restart.service only restarts containers with restart-policy
# `always` (see compose.yaml) on start of the user's systemd session —
# that's what makes the stack come back after a reboot.
run_as_app systemctl --user enable podman-restart.service 2>/dev/null || true

# podman-auto-update.timer checks daily for new upstream digests on every
# container labeled io.containers.autoupdate=registry (db/clamav/
# nginx in compose.yaml — not app, which is built locally) and rolls back
# automatically if the new image fails its healthcheck. Keeps base-image
# CVE patches flowing in without anyone having to notice and manually pull.
run_as_app systemctl --user enable --now podman-auto-update.timer 2>/dev/null || true

echo "==> Cloning / pulling repository"
# Run as $APP_USER, not root: $APP_DIR was just chowned to $APP_USER above,
# and a root-run clone/pull leaves .git itself root-owned underneath an
# attendance-owned parent — git's dubious-ownership check then refuses the
# next `pull` on every re-run of this script.
if [ -d "$APP_DIR/.git" ]; then
    run_as_app git -C "$APP_DIR" pull origin master
else
    run_as_app git clone "$REPO_URL" "$APP_DIR"
fi

echo "==> Setting up .env file"
if [ ! -f "$APP_DIR/.env" ]; then
    cat > "$APP_DIR/.env" <<EOF
# DB_HOST: use 'db' for the bundled PostgreSQL container (quick-start / no RDS).
# For AWS RDS: set to the RDS endpoint from 'terraform output rds_endpoint'
# and run ./init-letsencrypt.sh, which applies the compose.prod.yaml overlay.
DB_HOST=db
DB_USER=attendance_admin
DB_PASS=REPLACE_WITH_STRONG_PASSWORD
DB_NAME=employee_attendance
SECRET_KEY=$(openssl rand -hex 32)
# Encrypts PII (Aadhar/PAN/bank account) at rest — without this it's stored in plaintext.
ENCRYPTION_KEY=$(openssl rand -base64 32 | tr '+/' '-_')
APP_ENV=production
ADMIN_USERNAME=admin
ADMIN_PASSWORD=REPLACE_WITH_ADMIN_PASSWORD
# Public URL for password-reset and offer-letter email links.
# Use https://yourdomain.com when you have a domain; use http://YOUR_SERVER_IP for now.
APP_URL=REPLACE_WITH_URL
# CORS: set to your domain when live, e.g. https://yourdomain.com
ALLOWED_ORIGINS=*
EOF
    echo "    .env created — fill in the REPLACE_WITH_* values at $APP_DIR/.env, then re-run this script"
fi

cd "$APP_DIR"
if grep -q "REPLACE_WITH" .env; then
    echo ""
    echo "====================================================="
    echo "  .env still has REPLACE_WITH_* placeholders."
    echo "  Edit $APP_DIR/.env, then re-run deploy.sh to start the app."
    echo "====================================================="
    exit 0
fi

echo "==> Setting up file-based DB secret (read by compose.yaml's secrets:)"
mkdir -p secrets
if [ ! -f secrets/db_pass.txt ]; then
    # Kept in sync with DB_PASS above — the app reads DB_PASS from .env
    # directly, while Postgres reads POSTGRES_PASSWORD_FILE, so both need
    # the same value. Postgres has no separate root/superuser secret the
    # way MySQL did (POSTGRES_USER already is the superuser), so this is
    # the only secret file needed now.
    grep '^DB_PASS=' .env | cut -d= -f2- > secrets/db_pass.txt
fi
chmod 600 secrets/db_pass.txt

echo "==> Generating internal app<->nginx cert (if missing)"
# compose.yaml bind-mounts ./cert.pem and ./key.pem from the host; if they
# don't exist yet, Podman creates an empty directory at that path instead of
# failing, which breaks gunicorn's SSL startup. This is only used for the
# nginx->app hop internally (nginx terminates the real cert from certbot).
if [ ! -f cert.pem ] || [ ! -f key.pem ]; then
    openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
        -keyout key.pem -out cert.pem -subj "/CN=localhost"
fi
# World-readable: see compose.yaml's comment on rootless container UID
# mapping. Low-sensitivity — internal nginx<->app TLS hop only.
chmod 644 cert.pem key.pem

echo "==> Rendering nginx.conf (HTTP-only for IP access; will be replaced by init-letsencrypt.sh once you have a domain)"
if [ ! -f "$APP_DIR/nginx/nginx.conf" ]; then
    cat > "$APP_DIR/nginx/nginx.conf" <<'NGINXEOF'
upstream app {
    server app:5000;
}

# Same zones as nginx/nginx.conf.template — kept in sync so this temporary
# HTTP-only config has the same defense-in-depth rate limiting before a
# domain/HTTPS is set up, not just after.
#
# rate=30r/m (not the tighter 5r/m you'd normally pick for a login endpoint):
# under rootless Podman's port-forwarding proxy, every external visitor's
# source IP is collapsed to the same internal gateway address before nginx
# ever sees it (verified 2026-07-31 — mobile, desktop, and bot traffic all
# showed as one IP in access logs), so this bucket is effectively shared by
# the whole site's traffic combined, not per-visitor. A tight per-IP-style
# limit here locks out every real user after a handful of page reloads by
# anyone. The app's own Flask-Limiter (300/min) and mandatory email-OTP MFA
# are the real brute-force defenses; this is just a backstop. Revisit once
# nginx can see real client IPs again (host networking, or pasta-based
# publishing instead of the rootlessport proxy).
limit_req_zone $binary_remote_addr zone=login:10m rate=30r/m;
limit_req_zone $binary_remote_addr zone=general:10m rate=20r/s;
limit_conn_zone $binary_remote_addr zone=perip:10m;

# Same gzip block as nginx/nginx.conf.template — kept in sync so payloads are
# compressed for mobile connections even before a domain/HTTPS is set up.
gzip on;
gzip_vary on;
gzip_proxied any;
gzip_comp_level 6;
gzip_min_length 256;
gzip_types text/plain text/css application/json application/javascript text/javascript text/xml application/xml image/svg+xml;

server {
    # See the ufw before.rules NAT block above — public 80 is redirected to
    # this host port before it reaches nginx, which runs unprivileged.
    listen 8080;
    server_name _;

    client_max_body_size 20M;
    limit_conn perip 20;

    location ~ ^/(admin_login|employee_login|api/login|api/employee/login) {
        limit_req zone=login burst=20 nodelay;
        proxy_pass         https://app;
        proxy_ssl_verify   off;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
        proxy_connect_timeout 10s;
    }

    location /static/ {
        alias /app/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        limit_req zone=general burst=40 nodelay;
        proxy_pass         https://app;
        proxy_ssl_verify   off;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }
}
NGINXEOF
    chmod 644 "$APP_DIR/nginx/nginx.conf" # world-readable, same reason as cert.pem/key.pem above
    echo "    nginx.conf written (HTTP-only). Run ./init-letsencrypt.sh <domain> <email> later to add HTTPS."
fi

echo "==> Handing ownership of $APP_DIR to $APP_USER"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo "==> Building and starting full stack (app + PostgreSQL + Redis + nginx) as $APP_USER"
COMPOSE="podman-compose"
run_as_app $COMPOSE build app
run_as_app $COMPOSE up -d
# When you add a domain and want HTTPS + RDS, run ./init-letsencrypt.sh
# (it applies the compose.prod.yaml overlay the same way, after editing
# DB_HOST in .env to point at your RDS endpoint)

echo "==> Scheduling daily nginx reload (so renewed certs take effect)"
# `crontab -l` fails (no crontab yet) on a fresh box — `|| true` keeps that
# from tripping `set -e` and aborting the script before it reaches the end.
# This stays in root's crontab (root always has one) but drops into the app
# user's rootless podman context via the same runuser+env pattern as
# run_as_app — a plain crontab entry can't call a bash function defined
# earlier in this script.
CRON_CMD="cd $APP_DIR && runuser -u $APP_USER -- env XDG_RUNTIME_DIR=/run/user/$APP_UID HOME=/home/$APP_USER $COMPOSE exec -T nginx nginx -s reload >/dev/null 2>&1"
( crontab -l 2>/dev/null | grep -v "nginx -s reload" || true; \
  echo "30 3 * * * $CRON_CMD" ) | crontab -

echo ""
echo "====================================================="
echo "  Stack is up! Access the app at:"
echo "    http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo YOUR_SERVER_IP)"
echo ""
echo "  NEXT STEPS:"
echo "  1. Complete setup at http://YOUR_IP/setup"
echo "  2. When you add a domain, run:"
echo "       ./init-letsencrypt.sh yourdomain.com your@email.com"
echo "     This switches nginx to HTTPS + gets a trusted cert."
echo "====================================================="
echo "  Useful commands (as root, or SSH in as $APP_USER and drop the prefix):"
echo "    runuser -u $APP_USER -- env XDG_RUNTIME_DIR=/run/user/$APP_UID podman-compose logs -f app"
echo "    runuser -u $APP_USER -- env XDG_RUNTIME_DIR=/run/user/$APP_UID podman-compose restart app"
echo "    runuser -u $APP_USER -- env XDG_RUNTIME_DIR=/run/user/$APP_UID podman-compose down"
echo "====================================================="
