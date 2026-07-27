# ------------------------------------------------------------------------------
# AWS BASTION & CLIENT VPN - SECURE ADMIN ACCESS BLUEPRINT WITH MFA
# ------------------------------------------------------------------------------

resource "aws_security_group" "bastion_sg" {
  name        = "${var.environment}-bastion-sg"
  description = "Security Group for Admin SSH Bastion / VPN Endpoint"
  vpc_id      = aws_vpc.main.id

  # Port 22 restricted strictly to admin IP CIDRs or AWS Systems Manager Session Manager
  ingress {
    description = "SSH Access from Authorized Admin Office IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.admin_allowed_cidr_blocks
  }

  egress {
    description = "Allow Bastion to connect to PostgreSQL RDS on Port 5432"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    security_groups = [aws_security_group.db_sg.id]
  }

  tags = {
    Name        = "${var.environment}-bastion-sg"
    Environment = var.environment
  }
}

# IAM Role for SSM Session Manager (No open SSH ports required)
resource "aws_iam_role" "bastion_ssm_role" {
  name = "${var.environment}-bastion-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "bastion_ssm_attach" {
  role       = aws_iam_role.bastion_ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "bastion_profile" {
  name = "${var.environment}-bastion-instance-profile"
  role = aws_iam_role.bastion_ssm_role.name
}

resource "aws_instance" "bastion" {
  ami                  = var.bastion_ami_id
  instance_type        = "t3.micro"
  subnet_id            = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.bastion_sg.id]
  iam_instance_profile = aws_iam_instance_profile.bastion_profile.name

  metadata_options {
    http_tokens                 = "required" # Enforce IMDSv2
    http_put_response_hop_limit = 1
  }

  root_block_device {
    encrypted   = true
    volume_size = 20
  }

  tags = {
    Name        = "${var.environment}-bastion-host"
    Environment = var.environment
  }
}
