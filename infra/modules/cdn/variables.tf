variable "environment" {
  type        = string
  description = "The deployment environment (e.g., dev, prod)"
}

variable "alb_dns_name" {
  type        = string
  description = "DNS name of the ALB which will be the CloudFront origin"
}

variable "cloudfront_header_secret" {
  type        = string
  description = "Secret header value to ensure ALB only accepts traffic from CloudFront"
  sensitive   = true
}
