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

variable "swagger_username" {
  type        = string
  description = "Username for Swagger UI documentation"
  default     = "admin"
}

variable "swagger_password" {
  type        = string
  description = "Password for Swagger UI documentation"
  default     = "changeme"
  sensitive   = true
}

variable "cloudfront_header_secret" {
  type        = string
  description = "Secret header value to ensure ALB only accepts traffic from CloudFront"
  default     = "X-CycleLink-CloudFront-Secret-123"
  sensitive   = true
}

variable "cdn_base_url" {
  type        = string
  description = "Base URL of the CloudFront distribution (if any)"
  default     = ""
}

variable "alert_email" {
  type        = string
  description = "Email address to receive critical error alerts via SNS"
}
