output "s3_bucket_name" {
  value       = aws_s3_bucket.cyclelink_s3_bucket.bucket
  description = "The name of the created S3 bucket"
}

output "db_endpoint" {
  value       = aws_db_instance.cyclelink_db.endpoint
  description = "The database endpoint (hostname:port)"
}

output "db_address" {
  value       = aws_db_instance.cyclelink_db.address
  description = "The database hostname"
}

output "db_port" {
  value       = aws_db_instance.cyclelink_db.port
  description = "The port the database is listening on"
}

output "db_name" {
  value       = aws_db_instance.cyclelink_db.db_name
  description = "The name of the database"
}
