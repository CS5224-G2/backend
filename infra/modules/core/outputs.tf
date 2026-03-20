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

#### MongoDB Atlas Outputs ####
output "atlas_cluster_connection_string" {
  value       = mongodbatlas_advanced_cluster.cyclelink.connection_strings[0].standard_srv
  description = "MongoDB Atlas SRV connection string (mongodb+srv://...)"
}

output "atlas_project_id" {
  value       = mongodbatlas_project.cyclelink.id
  description = "MongoDB Atlas Project ID"
}
