variable "environment" {
  type        = string
  description = "The deployment environment (e.g., dev, prod)"
}

variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "ap-southeast-1"
}

# ── Alert Recipient ─────────────────────────────────────────────────
variable "alert_email" {
  type        = string
  description = "Email address to receive critical error alerts"
}

# ── Log Groups to monitor ───────────────────────────────────────────
variable "backend_log_group_name" {
  type        = string
  description = "CloudWatch Log Group name for the backend ECS service"
}

variable "bike_route_log_group_name" {
  type        = string
  description = "CloudWatch Log Group name for the bike-route ECS service"
}

