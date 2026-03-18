resource "aws_s3_bucket" "cyclelink_s3_bucket" {
  bucket        = "cyclelink-${var.environment}-s3-bucket" 
}

resource "aws_db_instance" "cyclelink_db" {
  identifier          = "cyclelink-${var.environment}-db"
  
  engine              = "postgres"
  engine_version      = "18.3"
  instance_class      = "db.t4g.micro" # Free tier eligible
  allocated_storage   = 20 # Free tier eligible
  
  db_name             = "cyclelink"
  username            = var.db_username
  password            = var.db_password
  
  skip_final_snapshot       = false
  snapshot_identifier       = var.snapshot_identifier
  final_snapshot_identifier = "cyclelink-${var.environment}-db-final-snapshot"
  
  publicly_accessible = var.db_publicly_accessible
}
