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

# ==========================================
# 1. NETWORKING (VPC, Subnets, IGW, NAT)
# ==========================================
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = { Name = "hrms-prod-vpc" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 4, count.index)
  map_public_ip_on_launch = true
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  tags = { Name = "hrms-public-subnet-${count.index + 1}" }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 4, count.index + 2)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags = { Name = "hrms-private-subnet-${count.index + 1}" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags = { Name = "hrms-igw" }
}

resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  tags = { Name = "hrms-nat" }
}

resource "aws_eip" "nat" {
  domain = "vpc"
}

# ==========================================
# 2. SECURITY GROUPS
# ==========================================
resource "aws_security_group" "alb_sg" {
  name        = "hrms-alb-sg"
  description = "Allow HTTPS and HTTP inbound"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs_sg" {
  name        = "hrms-ecs-sg"
  description = "Allow inbound from ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "rds_sg" {
  name        = "hrms-rds-sg"
  description = "Allow PostgreSQL from ECS"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_sg.id]
  }
}

resource "aws_security_group" "redis_sg" {
  name        = "hrms-redis-sg"
  description = "Allow Redis from ECS"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_sg.id]
  }
}

# ==========================================
# 3. DATABASE (Amazon RDS PostgreSQL)
# ==========================================
resource "aws_db_subnet_group" "rds_subnet_group" {
  name       = "hrms-rds-subnet-group"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "postgres" {
  identifier             = "hrms-prod-db"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = "db.t4g.medium"
  allocated_storage      = 50
  storage_type           = "gp3"
  db_name                = "hrms_prod"
  username               = var.db_username
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.rds_subnet_group.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  skip_final_snapshot    = true
  multi_az               = true
}

# ==========================================
# 4. CACHE (Amazon ElastiCache Redis)
# ==========================================
resource "aws_elasticache_subnet_group" "redis_subnet_group" {
  name       = "hrms-redis-subnet-group"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "hrms-prod-redis"
  engine               = "redis"
  node_type            = "cache.t4g.small"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  subnet_group_name    = aws_elasticache_subnet_group.redis_subnet_group.name
  security_group_ids   = [aws_security_group.redis_sg.id]
}

# ==========================================
# 5. STORAGE (Amazon S3 with Lifecycle Rules)
# ==========================================
resource "aws_s3_bucket" "app_storage" {
  bucket = "hrms-prod-assets-${random_id.s3_suffix.hex}"
}

resource "aws_s3_bucket_lifecycle_configuration" "app_storage_lifecycle" {
  bucket = aws_s3_bucket.app_storage.id

  rule {
    id     = "expire_garbage"
    status = "Enabled"
    filter {
      prefix = "garbage/"
    }
    expiration {
      days = 30
    }
  }

  rule {
    id     = "expire_cache"
    status = "Enabled"
    filter {
      prefix = "cache/"
    }
    expiration {
      days = 30
    }
  }
}

resource "random_id" "s3_suffix" {
  byte_length = 4
}

# ==========================================
# 6. LOAD BALANCING (Application Load Balancer)
# ==========================================
resource "aws_lb" "alb" {
  name               = "hrms-prod-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = aws_subnet.public[*].id
}

resource "aws_lb_target_group" "ecs_tg" {
  name        = "hrms-ecs-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/healthz"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.alb.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ecs_tg.arn
  }
}

# ==========================================
# 7. COMPUTE (AWS ECS Fargate Cluster)
# ==========================================
resource "aws_ecs_cluster" "fargate_cluster" {
  name = "hrms-prod-cluster"
}

# Data source for availability zones
data "aws_availability_zones" "available" {}

# Variables
variable "aws_region" {
  default = "us-east-1"
}
variable "db_username" {
  sensitive = true
}
variable "db_password" {
  sensitive = true
}
