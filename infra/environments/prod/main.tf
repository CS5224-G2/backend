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

  db_publicly_accessible = false
  
  db_username            = var.db_username
  db_password            = var.db_password
  snapshot_identifier    = var.snapshot_identifier
}
