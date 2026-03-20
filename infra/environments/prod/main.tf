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
