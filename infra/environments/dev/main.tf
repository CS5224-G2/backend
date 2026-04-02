terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "ap-southeast-1"
}

module "core" {
  source      = "../../modules/core"
  environment = "dev"

  resource_publicly_accessible = true
  
  rds_username            = var.rds_username
  rds_password            = var.rds_password
  rds_snapshot_identifier    = var.rds_snapshot_identifier
}

module "lambda" {
  source      = "../../modules/lambda"
  environment = "dev"

  s3_bucket_name          = module.core.s3_bucket_name
  enable_weather_schedule = true

  vpc_id               = module.core.vpc_id
  subnet_ids           = module.core.subnet_ids
  security_group_id    = module.core.security_group_id
  elasticache_endpoint = module.core.elasticache_endpoint
  elasticache_port     = module.core.elasticache_port
}

module "ecs" {
  source      = "../../modules/ecs"
  environment = "dev"

  vpc_id            = module.core.vpc_id
  subnet_ids        = module.core.subnet_ids
  security_group_id = module.core.security_group_id

  places_db_url   = "postgresql+asyncpg://${var.rds_username}:${var.rds_password}@${module.core.rds_address}:${module.core.rds_port}/${module.core.rds_name}?ssl=require"
  secret_key      = var.secret_key
  allowed_origins = var.allowed_origins
  s3_bucket_name  = module.core.s3_bucket_name
  mongodb_url     = var.mongodb_url
  swagger_username = var.swagger_username
  swagger_password = var.swagger_password

  # Redis / ElastiCache
  redis_host = module.core.elasticache_endpoint
  redis_port = module.core.elasticache_port
  redis_ssl  = true

  # CloudFront Security
  cloudfront_header_secret = var.cloudfront_header_secret
  cdn_base_url = var.cdn_base_url
}

module "cdn" {
  source      = "../../modules/cdn"
  environment = "dev"

  alb_dns_name             = module.ecs.alb_dns_name
  cloudfront_header_secret = var.cloudfront_header_secret
  s3_bucket_arn            = module.core.s3_bucket_arn
  s3_bucket_name           = module.core.s3_bucket_name
  s3_bucket_domain_name    = module.core.s3_bucket_domain_name
}

module "waf" {
  source      = "../../modules/waf"
  environment = "dev"

  resource_arn = module.ecs.alb_arn
}
