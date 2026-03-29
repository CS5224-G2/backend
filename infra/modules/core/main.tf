# Find the default VPC so we can create a security group in it
# TODO: We might have to create a custom VPC in future
data "aws_vpc" "default" {
  default = true
}

# Discover all default subnets in the default VPC
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

# Security Group
resource "aws_security_group" "cyclelink_sg" {
  name        = "cyclelink-${var.environment}-sg"
  description = "Allow inbound traffic for CycleLink resources"
  vpc_id      = data.aws_vpc.default.id

  # PostgreSQL Access
  ingress {
    description = "PostgreSQL Access"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.resource_publicly_accessible ? ["0.0.0.0/0"] : [data.aws_vpc.default.cidr_block]
  }

  # Redis/Valkey Access
  ingress {
    description = "Redis/Valkey Access"
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    self        = true
  }

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    ignore_changes = [ingress]
  }
}

# S3 Bucket
resource "aws_s3_bucket" "cyclelink_s3_bucket" {
  bucket        = "cyclelink-${var.environment}-s3-bucket" 
}

# RDS
resource "aws_db_instance" "cyclelink_db" {
  identifier          = "cyclelink-${var.environment}-db"
  
  engine              = "postgres"
  engine_version      = "18.3"
  instance_class      = "db.t4g.micro" # Free tier eligible
  allocated_storage   = 20 # Free tier eligible
  
  db_name             = "cyclelink"
  username            = var.rds_username
  password            = var.rds_password
  
  skip_final_snapshot       = false
  snapshot_identifier       = var.rds_snapshot_identifier
  final_snapshot_identifier = "cyclelink-${var.environment}-db-final-snapshot"
  
  publicly_accessible    = var.resource_publicly_accessible
  vpc_security_group_ids = [aws_security_group.cyclelink_sg.id]
}

# ElastiCache Valkey Serverless
resource "aws_elasticache_serverless_cache" "cache" {
  name = "cyclelink-${var.environment}-cache"
  engine = "valkey"
  
  description = "Serverless Valkey cache for CycleLink"
  
  subnet_ids         = data.aws_subnets.default.ids
  security_group_ids = [aws_security_group.cyclelink_sg.id]
}
