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
  description = "The name of the snapshot to restore from. Leave null to create a brand new RDS."
  default     = null
}

variable "docdb_username" {
  type        = string
  description = "Username for DocumentDB"
}

variable "docdb_password" {
  type        = string
  description = "Master password for DocumentDB"
  sensitive   = true
}
