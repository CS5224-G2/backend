############################################################
# SNS Topic — Critical Error Alerts
############################################################
resource "aws_sns_topic" "critical_errors" {
  name = "cyclelink-${var.environment}-critical-errors"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.critical_errors.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

############################################################
# Metric Filters — Detect critical errors in ECS logs
############################################################

# Backend: match CRITICAL, ERROR, or Traceback in logs
resource "aws_cloudwatch_log_metric_filter" "backend_critical" {
  name           = "cyclelink-${var.environment}-backend-critical-errors"
  log_group_name = var.backend_log_group_name
  pattern        = "?CRITICAL ?\"ERROR\" ?\"Traceback\" ?\"Internal Server Error\""

  metric_transformation {
    name          = "BackendCriticalErrorCount"
    namespace     = "CycleLink/${var.environment}"
    value         = "1"
    default_value = "0"
  }
}

# Bike Route: same pattern
resource "aws_cloudwatch_log_metric_filter" "bike_route_critical" {
  name           = "cyclelink-${var.environment}-bikeroute-critical-errors"
  log_group_name = var.bike_route_log_group_name
  pattern        = "?CRITICAL ?\"ERROR\" ?\"Traceback\" ?\"Internal Server Error\""

  metric_transformation {
    name          = "BikeRouteCriticalErrorCount"
    namespace     = "CycleLink/${var.environment}"
    value         = "1"
    default_value = "0"
  }
}

############################################################
# CloudWatch Alarms — fire when error count spikes
############################################################

# Backend critical error alarm (≥ 5 errors in 5 min)
resource "aws_cloudwatch_metric_alarm" "backend_critical_errors" {
  alarm_name          = "cyclelink-${var.environment}-backend-critical-errors"
  alarm_description   = "Critical errors detected in backend ECS service logs"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "BackendCriticalErrorCount"
  namespace           = "CycleLink/${var.environment}"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.critical_errors.arn]
  ok_actions    = [aws_sns_topic.critical_errors.arn]
}

# Bike-route critical error alarm (≥ 5 errors in 5 min)
resource "aws_cloudwatch_metric_alarm" "bike_route_critical_errors" {
  alarm_name          = "cyclelink-${var.environment}-bikeroute-critical-errors"
  alarm_description   = "Critical errors detected in bike-route ECS service logs"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "BikeRouteCriticalErrorCount"
  namespace           = "CycleLink/${var.environment}"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.critical_errors.arn]
  ok_actions    = [aws_sns_topic.critical_errors.arn]
}

