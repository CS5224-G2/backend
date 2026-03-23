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
  environment = "prod"

  resource_publicly_accessible = false
  
  rds_username            = var.rds_username
  rds_password            = var.rds_password
  rds_snapshot_identifier    = var.rds_snapshot_identifier
}

module "lambda" {
  source      = "../../modules/lambda"
  environment = "prod"

  s3_bucket_name          = module.core.s3_bucket_name
  enable_weather_schedule = true
}

module "ecs" {
  source      = "../../modules/ecs"
  environment = "prod"

  vpc_id            = module.core.vpc_id
  subnet_ids        = module.core.subnet_ids
  security_group_id = module.core.security_group_id

  places_db_url   = "postgresql+asyncpg://${var.rds_username}:${var.rds_password}@${module.core.rds_address}:${module.core.rds_port}/${module.core.rds_name}?ssl=require"
  secret_key      = var.secret_key
  allowed_origins = var.allowed_origins
  s3_bucket_name  = module.core.s3_bucket_name
}


