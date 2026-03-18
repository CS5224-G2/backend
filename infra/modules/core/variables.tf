variable "environment" {
  type        = string
  description = "The deployment environment (e.g., dev, prod)"
}

variable "db_publicly_accessible" {
  type        = bool
  description = "Should the database have a public IP for local access?"
  default     = false
}

variable "db_password" {
  type        = string
  description = "Master password for the database"
  sensitive   = true
}

variable "db_username" {
  type        = string
  description = "Username for the database"
}

variable "snapshot_identifier" {
  type        = string
  description = "The name of the snapshot to restore from. Leave null to create a brand new DB."
  default     = null
}
