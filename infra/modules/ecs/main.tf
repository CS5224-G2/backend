############################################################
# ECR — Container Registry
############################################################
resource "aws_ecr_repository" "backend" {
  name                 = "cyclelink-${var.environment}-backend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "bike_route" {
  name                 = "cyclelink-${var.environment}-bike-route"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}



############################################################
# CloudWatch Logs
############################################################
resource "aws_cloudwatch_log_group" "ecs_backend" {
  name              = "/ecs/cyclelink-${var.environment}-backend"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "ecs_bike_route" {
  name              = "/ecs/cyclelink-${var.environment}-bike-route"
  retention_in_days = 30
}

############################################################
# IAM — Task Execution Role (ECR pull + CloudWatch)
############################################################
resource "aws_iam_role" "ecs_task_execution" {
  name = "cyclelink-${var.environment}-ecs-task-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

############################################################
# IAM — Task Role (permissions the app itself needs)
############################################################
resource "aws_iam_role" "ecs_task" {
  name = "cyclelink-${var.environment}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

# Grant read access to the S3 bucket
resource "aws_iam_role_policy" "ecs_s3_read" {
  name = "cyclelink-${var.environment}-ecs-s3-read"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:ListBucket"]
      Resource = [
        "arn:aws:s3:::${var.s3_bucket_name}",
        "arn:aws:s3:::${var.s3_bucket_name}/*"
      ]
    }]
  })
}

# Grant read access to CloudWatch metrics and logs for the admin dashboard
resource "aws_iam_role_policy" "ecs_cloudwatch_read" {
  name = "cyclelink-${var.environment}-ecs-cw-read"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics",
          "logs:StartQuery",
          "logs:GetQueryResults",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

############################################################
# Security Group Rules (Attaching to Core SG)
############################################################
resource "aws_security_group_rule" "alb_http" {
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = var.security_group_id
  description       = "HTTP to ALB"
}

resource "aws_security_group_rule" "alb_https" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = var.security_group_id
  description       = "HTTPS to ALB"
}

resource "aws_security_group_rule" "ecs_from_alb" {
  type                     = "ingress"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  security_group_id        = var.security_group_id
  source_security_group_id = var.security_group_id
  description              = "Allow ECS tasks to receive traffic from ALB (same SG)"
}

resource "aws_security_group_rule" "rds_from_ecs" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = var.security_group_id
  source_security_group_id = var.security_group_id
  description              = "Allow RDS to receive traffic from ECS tasks (same SG)"
}

############################################################
# ALB
############################################################
resource "aws_lb" "backend" {
  name               = "cyclelink-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.security_group_id]
  subnets            = var.subnet_ids
}

resource "aws_lb_target_group" "backend" {
  name        = "cyclelink-${var.environment}-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.backend.arn
  port              = 80
  protocol          = "HTTP"

  # Default action returns 403 Forbidden
  default_action {
    type = "fixed-response"

    fixed_response {
      content_type = "text/plain"
      message_body = "Access Denied: Please access the website via CloudFront"
      status_code  = "403"
    }
  }
}

# Main Backend Forwarding Rule
resource "aws_lb_listener_rule" "main_backend" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    http_header {
      http_header_name = "X-Custom-Header"
      values           = [var.cloudfront_header_secret]
    }
  }
}

resource "aws_lb_target_group" "bike_route" {
  name        = "cyclelink-${var.environment}-br-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
  }
}

resource "aws_lb_listener_rule" "bike_route" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.bike_route.arn
  }

  condition {
    path_pattern {
      values = ["/v1/route-suggestion*"]
    }
  }

  # Also restrict bike_route access to CloudFront
  condition {
    http_header {
      http_header_name = "X-Custom-Header"
      values           = [var.cloudfront_header_secret]
    }
  }
}




############################################################
# ECS Cluster
############################################################
resource "aws_ecs_cluster" "main" {
  name = "cyclelink-${var.environment}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

############################################################
# ECS Task Definition
############################################################
resource "aws_ecs_task_definition" "backend" {
  family                   = "cyclelink-${var.environment}-backend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "backend"
    image     = "${aws_ecr_repository.backend.repository_url}:latest"
    essential = true

    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]

    environment = [
      { name = "ENVIRONMENT",     value = var.environment },
      { name = "PLACES_DB_URL",   value = var.places_db_url },
      { name = "SECRET_KEY",      value = var.secret_key },
      { name = "ALLOWED_ORIGINS", value = jsonencode([for o in split(",", var.allowed_origins) : trimspace(o) if trimspace(o) != ""]) },
      { name = "SERVICE_URLS",    value = var.service_urls },
      { name = "MONGODB_URL",     value = var.mongodb_url },
      { name = "REDIS_HOST",      value = var.redis_host },
      { name = "REDIS_PORT",      value = tostring(var.redis_port) },
      { name = "REDIS_SSL",       value = tostring(var.redis_ssl) },
      { name = "SWAGGER_USERNAME", value = var.swagger_username },
      { name = "SWAGGER_PASSWORD", value = var.swagger_password },
      { name = "AWS_REGION",       value = var.aws_region },
      { name = "S3_BUCKET_NAME",   value = var.s3_bucket_name },
      { name = "CDN_BASE_URL",     value = var.cdn_base_url },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs_backend.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "backend"
      }
    }
  }])
}

############################################################
# ECS Service
############################################################
resource "aws_ecs_service" "backend" {
  name            = "cyclelink-${var.environment}-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [var.security_group_id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http]
}

resource "aws_ecs_task_definition" "bike_route" {
  family                   = "cyclelink-${var.environment}-bike-route"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.bike_route_task_cpu
  memory                   = var.bike_route_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "bike-route"
    image     = "${aws_ecr_repository.bike_route.repository_url}:latest"
    essential = true

    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]

    environment = [
      { name = "ENVIRONMENT",     value = var.environment },
      { name = "PLACES_DB_URL",   value = var.places_db_url },
      { name = "SECRET_KEY",      value = var.secret_key },
      { name = "ALLOWED_ORIGINS", value = jsonencode([for o in split(",", var.allowed_origins) : trimspace(o) if trimspace(o) != ""]) },
      { name = "SERVICE_URLS",    value = var.service_urls },
      { name = "MONGODB_URL",     value = var.mongodb_url },
      { name = "S3_BUCKET_NAME",  value = var.s3_bucket_name },
      { name = "AWS_REGION",      value = var.aws_region },
      { name = "CDN_BASE_URL",    value = var.cdn_base_url },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs_bike_route.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "bike-route"
      }
    }
  }])
}

resource "aws_ecs_service" "bike_route" {
  name            = "cyclelink-${var.environment}-bike-route"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.bike_route.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [var.security_group_id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.bike_route.arn
    container_name   = "bike-route"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener_rule.bike_route]
}
