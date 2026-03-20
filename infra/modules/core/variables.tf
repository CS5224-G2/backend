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
