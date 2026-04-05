output "sns_topic_arn" {
  value       = aws_sns_topic.critical_errors.arn
  description = "ARN of the critical-errors SNS topic"
}
