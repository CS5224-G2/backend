#### S3 Outputs ####
output "s3_bucket_name" {
  value       = aws_s3_bucket.cyclelink_s3_bucket.bucket
}

#### RDS Outputs ####
output "rds_endpoint" {
  value       = aws_db_instance.cyclelink_db.endpoint
}

output "rds_address" {
  value       = aws_db_instance.cyclelink_db.address
}

output "rds_port" {
  value       = aws_db_instance.cyclelink_db.port
}

output "rds_name" {
  value       = aws_db_instance.cyclelink_db.db_name
}