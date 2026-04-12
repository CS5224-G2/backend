variable "environment" {
  type        = string
  description = "The deployment environment (e.g., dev, prod)"
}

variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "ap-southeast-1"
}

# ── Networking ───────────────────────────────────────────────────────
variable "vpc_id" {
  type        = string
  description = "VPC ID to deploy into"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs for ALB and ECS tasks"
}

variable "security_group_id" {
  type        = string
  description = "Existing Security Group ID to use for ALB and ECS Tasks"
}


# ── App Configuration ───────────────────────────────────────────────
variable "places_db_url" {
  type        = string
  description = "PostgreSQL connection string for the places database"
  sensitive   = true
}

variable "secret_key" {
  type        = string
  description = "JWT / session secret key"
  sensitive   = true
  default     = "changeme"
}

variable "allowed_origins" {
  type        = string
  description = "Comma-separated CORS origins"
  default     = "*"
}

variable "service_urls" {
  type        = string
  description = "JSON string of microservice URLs"
  default     = "{}"
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

variable "redis_host" {
  type        = string
  description = "Redis/ElastiCache host"
}

variable "redis_port" {
  type        = number
  description = "Redis/ElastiCache port"
  default     = 6379
}

variable "redis_ssl" {
  type        = bool
  description = "Whether to use SSL for Redis"
  default     = true
}


variable "s3_bucket_name" {
  type        = string
  description = "Name of the S3 bucket used by the app"
}

variable "sendgrid_api_key" {
  type        = string
  description = "SendGrid API Key"
  sensitive   = true
}

variable "sendgrid_from_email" {
  type        = string
  description = "SendGrid From Email"
}

# ── Task Sizing ─────────────────────────────────────────────────────
variable "task_cpu" {
  type        = string
  description = "Fargate task CPU units (256 = 0.25 vCPU)"
  default     = "256"
}

variable "task_memory" {
  type        = string
  description = "Fargate task memory in MiB"
  default     = "512"
}

variable "bike_route_task_cpu" {
  type        = string
  description = "Fargate task CPU units for the bike-route service"
  default     = "1024"
}

variable "bike_route_task_memory" {
  type        = string
  description = "Fargate task memory in MiB for the bike-route service (needs more for in-memory OSM graph)"
  default     = "2048"
}

variable "desired_count" {
  type        = number
  description = "Number of ECS tasks to run"
  default     = 1
}

variable "cloudfront_header_secret" {
  type        = string
  description = "Secret header value to ensure ALB only accepts traffic from CloudFront"
  default     = "X-CycleLink-CloudFront-Secret-123" # In production, this should be more secure and set via variables
  sensitive   = true
}

variable "cdn_base_url" {
  type        = string
  description = "Base URL of the CloudFront distribution (if any)"
  default     = ""
}
