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
  username            = var.rds_username
  password            = var.rds_password
  
  skip_final_snapshot       = false
  snapshot_identifier       = var.rds_snapshot_identifier
  final_snapshot_identifier = "cyclelink-${var.environment}-db-final-snapshot"
  
  publicly_accessible = var.rds_publicly_accessible
}

resource "aws_docdb_cluster" "cyclelink_docdb" {
  cluster_identifier      = "cyclelink-${var.environment}-docdb"
  engine                  = "docdb"
  master_username         = var.docdb_username
  master_password         = var.docdb_password
  
  skip_final_snapshot       = false
  final_snapshot_identifier = "cyclelink-${var.environment}-docdb-final-snapshot"
}

resource "aws_docdb_cluster_instance" "cyclelink_docdb_instance" {
  count              = 1
  identifier         = "cyclelink-${var.environment}-docdb-instance-${count.index}"
  cluster_identifier = aws_docdb_cluster.cyclelink_docdb.id
  instance_class     = "db.t3.medium" # Free tier eligible
}
