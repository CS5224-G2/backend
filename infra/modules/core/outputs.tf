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

#### Networking Outputs ####
output "vpc_id" {
  value       = data.aws_vpc.default.id
  description = "ID of the VPC"
}

output "subnet_ids" {
  value       = data.aws_subnets.default.ids
  description = "IDs of the default subnets"
}

output "security_group_id" {
  value       = aws_security_group.cyclelink_sg.id
  description = "ID of the CycleLink security group"
}

#### ElastiCache Outputs ####
output "elasticache_endpoint" {
  value       = aws_elasticache_serverless_cache.cache.endpoint[0].address
  description = "Address of the ElastiCache Valkey endpoint"
}

output "elasticache_port" {
  value       = aws_elasticache_serverless_cache.cache.endpoint[0].port
  description = "Port of the ElastiCache Valkey endpoint"
}