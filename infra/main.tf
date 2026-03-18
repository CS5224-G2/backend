terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "ap-southeast-1" # Singapore region
}

resource "aws_s3_bucket" "cyclelink_s3_bucket" {
  bucket        = "cyclelink-s3-bucket" 
}

resource "aws_db_instance" "cyclelink_db" {
  identifier          = "cyclelink-db"
  
  engine              = "postgres"
  engine_version      = "18.3"
  instance_class      = "db.t4g.micro"  # Free tier eligible, do not change
  allocated_storage   = 20  # Free tier eligible, do not change
  
  db_name             = "cyclelink"
  username            = var.db_username
  password            = var.db_password
  
  skip_final_snapshot       = false 
  publicly_accessible = false
  snapshot_identifier       = "cyclelink-db-final-snapshot"
  final_snapshot_identifier = "cyclelink-db-final-snapshot"
}
