# ── Alerting & uptime/error-rate monitoring ──────────────────────────────────
# Fills in resources several outputs in outputs.tf already referenced
# (sns_alert_topic_arn -> aws_sns_topic.alerts, dlm_required_instance_tag ->
# an EBS snapshot policy) but that were never actually written -- both were
# genuine gaps, not just missing monitoring: without aws_sns_topic.alerts,
# `terraform apply` fails outright on that output with "reference to
# undeclared resource".
#
# NOT independently verified against a real AWS account (no credentials
# were available in the environment this was written in) -- validated with
# `terraform fmt`/`terraform validate` only. Review with `terraform plan`
# before applying. Also note: this config has pre-existing, unrelated gaps
# (aws_db_instance.this, aws_iam_instance_profile.ec2_app_profile,
# aws_security_group.app_firewall are referenced in outputs.tf but not
# defined anywhere; variables.tf and main.tf each declare db_username/
# db_password, a duplicate-declaration error) that block `terraform
# validate`/`apply` for the whole config regardless of anything in this
# file -- out of scope for this change, flagged separately.

resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
  # Subscription sits in "pending confirmation" until the address clicks
  # the link AWS emails it -- see outputs.tf's sns_alert_topic_arn
  # description, which already calls this out.
}

# ── EC2 instance health (the app-server host itself) ─────────────────────────
# StatusCheckFailed catches both instance-level (hardware/hypervisor) and
# system-level (OS/network) failures -- the EC2-native equivalent of "is
# the box even up," independent of whether the app process inside it is
# healthy. Evaluated every minute since a downed host is exactly the kind
# of thing worth knowing about within 1-2 minutes, not 15.
resource "aws_cloudwatch_metric_alarm" "ec2_status_check_failed" {
  alarm_name          = "${var.project_name}-ec2-status-check-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "The app server EC2 instance is failing its status checks -- it may be unreachable."
  dimensions = {
    InstanceId = var.ec2_instance_id
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "ec2_cpu_high" {
  alarm_name          = "${var.project_name}-ec2-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "App server CPU has been above 85% for 15 minutes -- check for a runaway process or genuine capacity need before it degrades request latency."
  dimensions = {
    InstanceId = var.ec2_instance_id
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "ec2_mem_high" {
  # From cloudwatch-agent-config.json's own custom "CWAgent" namespace
  # metric (mem_used_percent) -- AWS/EC2's built-in metrics don't include
  # memory at all, only what the CloudWatch agent reports.
  alarm_name          = "${var.project_name}-ec2-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "mem_used_percent"
  namespace           = "CWAgent"
  period              = 300
  statistic           = "Average"
  threshold           = 90
  alarm_description   = "App server memory has been above 90% for 15 minutes."
  dimensions = {
    InstanceId = var.ec2_instance_id
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  # Only fires once the CloudWatch agent (cloudwatch-agent-config.json) is
  # actually installed and running on the instance and reporting this
  # metric -- otherwise this alarm just sits in INSUFFICIENT_DATA forever,
  # which is a visible, honest state (not a false "OK") rather than an
  # error.
}

# ── Application uptime (/healthz over the public internet) ──────────────────
# Only created when var.app_origin_domain is set (same conditional-creation
# pattern security_hardening.tf's CloudFront distribution already uses) --
# a Route53 health check needs a real public hostname to probe, and this is
# the one variable in this config that already carries that value.
resource "aws_route53_health_check" "app_healthz" {
  count             = var.app_origin_domain == "" ? 0 : 1
  fqdn              = var.app_origin_domain
  port              = 443
  type              = "HTTPS"
  resource_path     = "/healthz"
  failure_threshold = 3
  request_interval  = 30
  tags = {
    Name = "${var.project_name}-healthz"
  }
}

resource "aws_cloudwatch_metric_alarm" "healthz_down" {
  count = var.app_origin_domain == "" ? 0 : 1
  # Route53 health check metrics only exist in us-east-1 regardless of
  # where the rest of this stack is deployed -- a well-documented AWS
  # quirk, not a mistake here.
  provider            = aws.us_east_1
  alarm_name          = "${var.project_name}-healthz-down"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HealthCheckStatus"
  namespace           = "AWS/Route53"
  period              = 60
  statistic           = "Minimum"
  threshold           = 1
  alarm_description   = "GET https://${var.app_origin_domain}/healthz is failing from Route53's health-check network -- the app is likely unreachable to real users, not just from inside the VPC."
  dimensions = {
    HealthCheckId = aws_route53_health_check.app_healthz[0].id
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

# ── ECS/ALB error rate (only relevant if the ecs.tf deployment path is the
# one actually in use -- this repo's terraform config carries resources for
# both an existing-EC2-instance deployment (the rest of this file) and an
# ECS/Fargate one; aws_lb.app_alb only exists if ecs.tf is applied) ─────────
resource "aws_cloudwatch_metric_alarm" "alb_5xx_high" {
  alarm_name          = "${var.project_name}-alb-5xx-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "More than 10 5xx responses/minute from the app in two consecutive minutes."
  dimensions = {
    LoadBalancer = aws_lb.app_alb.arn_suffix
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "alb_unhealthy_targets" {
  # app_tg's own health check already probes /healthz (terraform/ecs.tf) --
  # this alarms on that check actually failing, the ECS-path equivalent of
  # ec2_status_check_failed above.
  alarm_name          = "${var.project_name}-alb-unhealthy-targets"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "At least one ECS task is failing its /healthz check."
  dimensions = {
    TargetGroup  = aws_lb_target_group.app_tg.arn_suffix
    LoadBalancer = aws_lb.app_alb.arn_suffix
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# ── Daily EBS snapshot of the app server's root volume ───────────────────────
# Fulfills outputs.tf's dlm_required_instance_tag output, which already
# documented this policy's existence and the tag it needs -- the policy
# resource itself just wasn't written. This is a full-disk backup (the
# whole app-server volume: uploaded files under private_uploads/,
# static/employee_docs/, dataset/, config, everything) -- complementary to,
# not a replacement for, the PostgreSQL-specific backups in
# scripts/backup_db.sh/RESTORE.md, which restore faster and don't require
# spinning up a whole replacement EC2 instance from a snapshot.
resource "aws_dlm_lifecycle_policy" "app_server_daily_snapshot" {
  description        = "Daily EBS snapshot of the ${var.project_name} app server"
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
        count = 14
      }
      tags_to_add = {
        SnapshotCreator = "dlm-${var.project_name}"
      }
      copy_tags = true
    }
  }
}

resource "aws_iam_role" "dlm_lifecycle_role" {
  name = "${var.project_name}-dlm-lifecycle-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "dlm.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "dlm_lifecycle_policy" {
  role       = aws_iam_role.dlm_lifecycle_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"
}
