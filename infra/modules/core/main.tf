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

  # DocumentDB Access
  ingress {
    description = "DocumentDB Access"
    from_port   = 27017
    to_port     = 27017
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

# DocumentDB
resource "aws_docdb_cluster" "cyclelink_docdb" {
  cluster_identifier      = "cyclelink-${var.environment}-docdb"
  engine                  = "docdb"
  master_username         = var.docdb_username
  master_password         = var.docdb_password
  
  skip_final_snapshot       = false
  final_snapshot_identifier = "cyclelink-${var.environment}-docdb-final-snapshot"
  vpc_security_group_ids    = [aws_security_group.cyclelink_sg.id]
}

resource "aws_docdb_cluster_instance" "cyclelink_docdb_instance" {
  count              = 1
  identifier         = "cyclelink-${var.environment}-docdb-instance-${count.index}"
  cluster_identifier = aws_docdb_cluster.cyclelink_docdb.id
  instance_class     = "db.t3.medium" # Free tier eligible
}
