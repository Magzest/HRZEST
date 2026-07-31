terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# CloudFront-scoped WAFv2 Web ACLs (scope = "CLOUDFRONT") must be created in
# us-east-1 regardless of var.aws_region — an AWS requirement, not a choice
# made here. Used only by aws_wafv2_web_acl.app in security_hardening.tf.
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

# ---------------------------------------------------------------------------
# RDS — PostgreSQL (replaces the containerized `db` service for production)
# ---------------------------------------------------------------------------

resource "aws_db_subnet_group" "this" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = var.subnet_ids

  tags = {
    Name = "${var.project_name}-db-subnet-group"
  }
}

resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "Allow PostgreSQL only from the application EC2 instance"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from app server"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.ec2_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-rds-sg"
  }
}

# ---------------------------------------------------------------------------
# App server firewall policy
#
#   OPEN (0.0.0.0/0)     — 80, 443: the only ports the public actually needs
#                           to reach (nginx redirects 80->443; 80 also serves
#                           the Let's Encrypt HTTP-01 challenge).
#   FILTERED (trusted IPs only) — 22 (SSH), 3389 (RDP), 5432/1433 (direct DB
#                           access), 8080/8443 (alternate HTTP/HTTPS) — never
#                           exposed to the internet, only to
#                           var.trusted_admin_cidrs. Several of these aren't
#                           actually used by this stack (RDP/1433 — this is a
#                           Linux/Postgres deployment, not Windows/MSSQL) but
#                           are still explicitly filtered rather than left
#                           unlisted, matching the requested policy.
#   CLOSED (no rule at all) — 21 (FTP), 23 (Telnet), 25 (SMTP): legacy
#                           cleartext protocols this app never runs; security
#                           groups default-deny anything not explicitly
#                           allowed, so "closed" means simply never adding a
#                           rule for them here.
#
# NOTE: this SG is a NEW Terraform-managed resource — it is not
# automatically attached to the existing EC2 instance (which was originally
# provisioned outside Terraform; see ec2_security_group_id). After `terraform
# apply`, attach this SG's ID to the instance (in addition to or in place of
# its current SG) via the EC2 console or:
#   aws ec2 modify-instance-attribute --instance-id <id> \
#     --groups <existing-sg-id> $(terraform output -raw app_firewall_sg_id)
resource "aws_security_group" "app_firewall" {
  name        = "${var.project_name}-app-firewall"
  description = "Public web ports open; management/DB ports filtered to trusted IPs; legacy ports closed"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP (redirects to HTTPS; also serves ACME HTTP-01 challenge)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH - filtered to trusted IPs only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.trusted_admin_cidrs
  }

  ingress {
    description = "RDP - filtered to trusted IPs only (not used by this Linux deployment, kept filtered per policy rather than unlisted)"
    from_port   = 3389
    to_port     = 3389
    protocol    = "tcp"
    cidr_blocks = var.trusted_admin_cidrs
  }

  ingress {
    description = "Direct PostgreSQL access - filtered to trusted IPs only (normal app traffic goes to RDS over the private VPC, not through here)"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.trusted_admin_cidrs
  }

  ingress {
    description = "MSSQL - filtered to trusted IPs only (not used by this stack, kept filtered per policy rather than unlisted)"
    from_port   = 1433
    to_port     = 1433
    protocol    = "tcp"
    cidr_blocks = var.trusted_admin_cidrs
  }

  ingress {
    description = "Alternate HTTP - filtered to trusted IPs only"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = var.trusted_admin_cidrs
  }

  ingress {
    description = "Alternate HTTPS - filtered to trusted IPs only"
    from_port   = 8443
    to_port     = 8443
    protocol    = "tcp"
    cidr_blocks = var.trusted_admin_cidrs
  }

  # 21 (FTP), 23 (Telnet), 25 (SMTP) deliberately have no ingress rule —
  # security groups default-deny, so this is what "closed" looks like.

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-app-firewall"
  }
}

resource "aws_db_instance" "this" {
  identifier     = "${var.project_name}-db"
  engine         = "postgres"
  engine_version = "16"

  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage
  storage_type      = "gp3"

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  backup_retention_period = var.db_backup_retention_days
  backup_window           = "17:00-18:00" # UTC — off-peak for Asia/Kolkata default
  maintenance_window      = "sun:18:30-sun:19:30"

  storage_encrypted = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.project_name}-db-final-snapshot"
  deletion_protection       = true

  tags = {
    Name = "${var.project_name}-db"
  }
}

# ---------------------------------------------------------------------------
# IAM — instance profile for the existing EC2 instance
# (CloudWatch agent metrics + read/write to the backup S3 bucket)
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "backups" {
  bucket = "${var.project_name}-backups-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-backups"
  }
}

resource "aws_s3_bucket_public_access_block" "backups" {
  bucket                  = aws_s3_bucket.backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "expire-old-backups"
    status = "Enabled"
    filter {}
    expiration {
      days = 30
    }
  }
}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2_app_role" {
  name               = "${var.project_name}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

resource "aws_iam_role_policy_attachment" "cloudwatch_agent" {
  role       = aws_iam_role.ec2_app_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

data "aws_iam_policy_document" "s3_backups_rw" {
  statement {
    actions   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.backups.arn, "${aws_s3_bucket.backups.arn}/*"]
  }
}

resource "aws_iam_role_policy" "s3_backups_rw" {
  name   = "${var.project_name}-s3-backups-rw"
  role   = aws_iam_role.ec2_app_role.id
  policy = data.aws_iam_policy_document.s3_backups_rw.json
}

resource "aws_iam_instance_profile" "ec2_app_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_app_role.name
}

# ---------------------------------------------------------------------------
# Monitoring — SNS alerts + CloudWatch alarms on the existing EC2 instance
# ---------------------------------------------------------------------------

resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "${var.project_name}-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "EC2 CPU above 80% for 15 minutes"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  dimensions = {
    InstanceId = var.ec2_instance_id
  }
}

resource "aws_cloudwatch_metric_alarm" "status_check_failed" {
  alarm_name          = "${var.project_name}-status-check-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "EC2 instance or system status check failed"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions = {
    InstanceId = var.ec2_instance_id
  }
}

resource "aws_cloudwatch_metric_alarm" "disk_high" {
  alarm_name          = "${var.project_name}-disk-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "disk_used_percent"
  namespace           = "CWAgent"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "Root volume disk usage above 85% (requires the CloudWatch agent — see cloudwatch-agent-config.json)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
  dimensions = {
    InstanceId = var.ec2_instance_id
    path       = "/"
    fstype     = "ext4"
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_storage_low" {
  alarm_name          = "${var.project_name}-rds-storage-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 2147483648 # 2 GiB in bytes
  alarm_description   = "RDS free storage below 2GB"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions = {
    DBInstanceIdentifier = aws_db_instance.this.id
  }
}

# ---------------------------------------------------------------------------
# Automated backups — EBS snapshots of the EC2 instance via DLM
# (covers the dataset/, static/employee_docs/, static/qrcodes/ Podman
#  volumes, which live on the instance's EBS volume and aren't in RDS)
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "dlm_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["dlm.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "dlm_lifecycle_role" {
  name               = "${var.project_name}-dlm-role"
  assume_role_policy = data.aws_iam_policy_document.dlm_assume_role.json
}

resource "aws_iam_role_policy_attachment" "dlm_lifecycle" {
  role       = aws_iam_role.dlm_lifecycle_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"
}

resource "aws_dlm_lifecycle_policy" "ec2_daily_snapshot" {
  description        = "Daily EBS snapshot of the attendance app server"
  execution_role_arn = aws_iam_role.dlm_lifecycle_role.arn
  state              = "ENABLED"

  policy_details {
    resource_types = ["INSTANCE"]

    target_tags = {
      DlmBackup = "${var.project_name}-app-server"
    }

    schedule {
      name = "daily-snapshot"
      create_rule {
        interval      = 24
        interval_unit = "HOURS"
        times         = ["03:00"]
      }
      retain_rule {
        count = 7
      }
      copy_tags = true
    }
  }
}
