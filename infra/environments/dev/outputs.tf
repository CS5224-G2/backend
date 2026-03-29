output "s3_bucket_name" {
  value = module.core.s3_bucket_name
}

output "rds_endpoint" {
  value = module.core.rds_endpoint
}

output "rds_address" {
  value = module.core.rds_address
}

output "rds_port" {
  value = module.core.rds_port
}

output "rds_name" {
  value = module.core.rds_name
}

output "fetch_weather_function_name" {
  value = module.lambda.fetch_weather_function_name
}

output "fetch_weather_function_arn" {
  value = module.lambda.fetch_weather_function_arn
}

#### ECS Outputs ####
output "ecr_repository_url" {
  value = module.ecs.ecr_repository_url
}

output "ecs_cluster_name" {
  value = module.ecs.ecs_cluster_name
}

output "ecs_service_name" {
  value = module.ecs.ecs_service_name
}

output "alb_dns_name" {
  value = module.ecs.alb_dns_name
}

output "elasticache_endpoint" {
  value       = module.core.elasticache_endpoint
  description = "Address of the ElastiCache Valkey endpoint"
}

output "elasticache_port" {
  value       = module.core.elasticache_port
  description = "Port of the ElastiCache Valkey endpoint"
}

output "cloudfront_domain_name" {
  value = module.cdn.cloudfront_domain_name
}

output "cloudfront_distribution_id" {
  value = module.cdn.cloudfront_distribution_id
}