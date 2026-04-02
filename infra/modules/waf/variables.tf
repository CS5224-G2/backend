variable "environment" {
  type        = string
  description = "Environment name (e.g. dev, prod)"
}

variable "resource_arn" {
  type        = string
  description = "The ARN of the resource to associate with the WAF (e.g. ALB ARN)"
}
