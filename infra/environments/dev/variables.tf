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

variable "secret_key" {
  type        = string
  description = "JWT / session secret key for the backend"
  sensitive   = true
  default     = "changeme"
}

variable "allowed_origins" {
  type        = string
  description = "Comma-separated CORS origins"
  default     = "*"
}

variable "mongodb_url" {
  type        = string
  description = "MongoDB Connection String"
  sensitive   = true
}

