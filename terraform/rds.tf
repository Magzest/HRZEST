# ------------------------------------------------------------------------------
# AWS RDS POSTGRESQL DATABASE - PRIVATE SUBNET ISOLATION & PORT HARDENING
# ------------------------------------------------------------------------------

resource "aws_db_subnet_group" "db_subnets" {
  name        = "${var.environment}-db-subnet-group"
  subnet_ids  = aws_subnet.private[*].id
  description = "Private Subnet Group for PostgreSQL RDS Engine"

  tags = {
    Name        = "${var.environment}-db-subnet-group"
    Environment = var.environment
  }
}

resource "aws_security_group" "db_sg" {
  name        = "${var.environment}-rds-db-sg"
  description = "Strict RDS Database SG - Accepts Port 5432 ONLY from App Containers & Bastion SG"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL Port 5432 Inbound from Application Container SG"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app_sg.id]
  }

  ingress {
    description     = "PostgreSQL Port 5432 Inbound from Authorized Bastion SG"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.bastion_sg.id]
  }

  tags = {
    Name        = "${var.environment}-rds-db-sg"
    Environment = var.environment
  }
}

resource "aws_db_instance" "postgresql" {
  identifier            = "${var.environment}-hrms-postgres"
  engine                = "postgres"
  engine_version        = "15.4"
  instance_class        = var.db_instance_class
  allocated_storage     = 50
  max_allocated_storage = 500
  storage_type          = "gp3"

  db_name  = "employee_attendance"
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.db_subnets.name
  vpc_security_group_ids = [aws_security_group.db_sg.id]

  publicly_accessible = false
  storage_encrypted   = true
  multi_az            = var.environment == "production" ? true : false

  backup_retention_period   = 30
  backup_window             = "03:00-04:00"
  maintenance_window        = "Mon:04:00-Mon:05:00"
  deletion_protection       = var.environment == "production" ? true : false
  skip_final_snapshot       = var.environment == "production" ? false : true
  final_snapshot_identifier = "${var.environment}-hrms-postgres-final-snapshot"

  tags = {
    Name        = "${var.environment}-hrms-postgres"
    Environment = var.environment
  }
}
