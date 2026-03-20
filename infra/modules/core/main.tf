# Find the default VPC so we can create a security group in it
# TODO: We might have to create a custom VPC in future
data "aws_vpc" "default" {
  default = true
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

# ============================================================
# MongoDB Atlas
# ============================================================

# Create a dedicated Atlas Project for this environment
resource "mongodbatlas_project" "cyclelink" {
  name   = "cyclelink-${var.environment}"
  org_id = var.atlas_org_id
}

# Free-tier (M0) shared cluster on AWS ap-southeast-1
resource "mongodbatlas_advanced_cluster" "cyclelink" {
  project_id   = mongodbatlas_project.cyclelink.id
  name         = "cyclelink-${var.environment}"
  cluster_type = "REPLICASET"

  replication_specs {
    region_configs {
      provider_name         = "TENANT"
      backing_provider_name = "AWS"
      region_name           = "AP_SOUTHEAST_1"
      priority              = 7

      electable_specs {
        instance_size = "M0"
      }
    }
  }
}

# Database User
resource "mongodbatlas_database_user" "cyclelink" {
  project_id         = mongodbatlas_project.cyclelink.id
  auth_database_name = "admin"
  username           = var.atlas_db_username
  password           = var.atlas_db_password

  roles {
    role_name     = "readWrite"
    database_name = "cyclelink"
  }
}

# Allow access from anywhere (dev) or restrict to known IPs (prod)
resource "mongodbatlas_project_ip_access_list" "cyclelink" {
  project_id = mongodbatlas_project.cyclelink.id
  cidr_block = var.atlas_ip_access_cidr
  comment    = "Managed by OpenTofu - ${var.environment}"
}
