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