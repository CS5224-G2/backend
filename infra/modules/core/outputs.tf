output "s3_bucket_name" {
  value       = aws_s3_bucket.cyclelink_s3_bucket.bucket
}

output "db_endpoint" {
  value       = aws_db_instance.cyclelink_db.endpoint
}

output "db_address" {
  value       = aws_db_instance.cyclelink_db.address
}

output "db_port" {
  value       = aws_db_instance.cyclelink_db.port
}

output "db_name" {
  value       = aws_db_instance.cyclelink_db.db_name
}
