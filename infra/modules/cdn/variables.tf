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

variable "s3_bucket_arn" {
  type        = string
  description = "ARN of the S3 bucket"
}

variable "s3_bucket_name" {
  type        = string
  description = "Name of the S3 bucket"
}

variable "s3_bucket_domain_name" {
  type        = string
  description = "Regional domain name of the S3 bucket"
}
