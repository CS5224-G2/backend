#### ECR Outputs ####
output "ecr_repository_url" {
  value       = aws_ecr_repository.backend.repository_url
  description = "URL of the ECR repository"
}

output "ecr_repository_name" {
  value       = aws_ecr_repository.backend.name
  description = "Name of the ECR repository"
}

#### ECS Outputs ####
output "ecs_cluster_name" {
  value       = aws_ecs_cluster.main.name
  description = "Name of the ECS cluster"
}

output "ecs_service_name" {
  value       = aws_ecs_service.backend.name
  description = "Name of the ECS service"
}

#### ALB Outputs ####
output "alb_dns_name" {
  value       = aws_lb.backend.dns_name
  description = "DNS name of the Application Load Balancer"
}

output "alb_zone_id" {
  value       = aws_lb.backend.zone_id
  description = "Route53 zone ID of the ALB (for alias records)"
}

output "alb_arn" {
  value       = aws_lb.backend.arn
  description = "The ARN of the Application Load Balancer"
}

#### Log Group Outputs ####
output "backend_log_group_name" {
  value       = aws_cloudwatch_log_group.ecs_backend.name
  description = "CloudWatch Log Group name for the backend service"
}

output "bike_route_log_group_name" {
  value       = aws_cloudwatch_log_group.ecs_bike_route.name
  description = "CloudWatch Log Group name for the bike-route service"
}
