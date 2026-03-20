variable "environment" {
  type        = string
  description = "The deployment environment (e.g., dev, prod)"
}

variable "resource_publicly_accessible" {
  type        = bool
  description = "Should the resource have a public IP for local access?"
  default     = false
}

variable "rds_password" {
  type        = string
  description = "Master password for RDS"
  sensitive   = true
}

variable "rds_username" {
  type        = string
  description = "Username for RDS"
}

variable "rds_snapshot_identifier" {
  type        = string
  description = "The name of the snapshot to restore from. Leave null to create a brand new DB."
  default     = null
}

#### MongoDB Atlas Variables ####

variable "atlas_org_id" {
  type        = string
  description = "MongoDB Atlas Organization ID"
}

variable "atlas_db_username" {
  type        = string
  description = "Username for the MongoDB Atlas database user"
}

variable "atlas_db_password" {
  type        = string
  description = "Password for the MongoDB Atlas database user"
  sensitive   = true
}

variable "atlas_ip_access_cidr" {
  type        = string
  description = "CIDR block to allow access to MongoDB Atlas (e.g., 0.0.0.0/0 for dev, specific IP for prod)"
  default     = "0.0.0.0/0"
}
