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

  docdb_username         = var.docdb_username
  docdb_password         = var.docdb_password
}
