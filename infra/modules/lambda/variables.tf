variable "environment" {
  type        = string
  description = "The deployment environment (e.g., dev, prod)"
}

variable "s3_bucket_name" {
  type        = string
  description = "Name of the S3 bucket to store weather data"
}


variable "enable_weather_schedule" {
  type        = bool
  description = "Enable the EventBridge schedule to invoke the fetch_weather Lambda"
  default     = false
}

variable "weather_schedule_expression" {
  type        = string
  description = "CloudWatch Events schedule expression for the weather Lambda"
  default     = "rate(5 minutes)"
}
