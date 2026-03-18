variable "db_username" {
  type        = string
  description = "Username for the database"
}

variable "db_password" {
  type        = string
  description = "Master password for the database"
  sensitive   = true
}

variable "snapshot_identifier" {
  type        = string
  description = "The name of the snapshot to restore from. Leave null to create a brand new DB."
  default     = null
}

variable "db_publicly_accessible" {
  type        = bool
  description = "Set to true to connect via a local tool like pgAdmin or DBeaver"
  default     = false
}
