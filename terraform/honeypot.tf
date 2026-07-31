# ---------------------------------------------------------------------------
# Honeypot security group — "system32_crypto_admin" (utils/honeypot.py,
# compose.yaml)
#
# A dedicated, SEPARATE security group rather than adding rules to
# aws_security_group.app_firewall (main.tf) on purpose: that SG already has
# 1433 (MSSQL) and 3389 (RDP) rules, but FILTERED to trusted_admin_cidrs —
# kept that way in case they're ever genuinely needed for management
# access. The honeypot needs the exact same port numbers OPEN TO THE PUBLIC
# instead (0.0.0.0/0) — that's the whole point, real attackers scanning the
# internet don't come from your trusted admin IPs. Reusing/widening the
# existing filtered rules would silently turn a "management access,
# restricted" port into "public, decoy" without that being obvious from
# reading main.tf in isolation. Two separate SGs keeps each one's intent
# legible on its own.
#
# NOT auto-attached to the EC2 instance — same "provisioned, attach
# deliberately" pattern as aws_security_group.app_firewall itself (see its
# own comment in main.tf). Opening these 6 ports is optional, real
# additional internet-facing attack surface (to an isolated decoy, not a
# real service) — attach only if you've also set ENABLE_HONEYPOT=1 in
# deploy.sh, or the ports open with nothing listening behind them.
# ---------------------------------------------------------------------------

resource "aws_security_group" "honeypot" {
  name        = "${var.project_name}-honeypot"
  description = "Decoy ports (system32_crypto_admin) open to the public on purpose - see utils/honeypot.py"
  vpc_id      = var.vpc_id

  ingress {
    description = "Decoy FTP"
    from_port   = 21
    to_port     = 21
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Decoy Telnet"
    from_port   = 23
    to_port     = 23
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Decoy SMTP"
    from_port   = 25
    to_port     = 25
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Decoy MSSQL"
    from_port   = 1433
    to_port     = 1433
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Decoy MySQL"
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Decoy RDP"
    from_port   = 3389
    to_port     = 3389
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    # Outbound only needs HTTPS to the alert webhook (utils/alerts.py) —
    # scoped to 443 rather than the app_firewall SG's all-ports egress,
    # since this process has no other legitimate reason to originate
    # outbound connections at all.
    description = "HTTPS to the security-alert webhook only"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-honeypot"
  }
}
