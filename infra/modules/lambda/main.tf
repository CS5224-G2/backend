#### IAM Role for Lambda Execution ####
resource "aws_iam_role" "lambda_exec" {
  name = "cyclelink-${var.environment}-lambda-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

# Allow Lambda to write logs to CloudWatch
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Allow Lambda to run in a VPC
resource "aws_iam_role_policy_attachment" "lambda_vpc_execution" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Allow Lambda to write weather data to S3
resource "aws_iam_role_policy" "lambda_s3_write" {
  name = "cyclelink-${var.environment}-lambda-s3-write"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject"]
        Resource = [
          "arn:aws:s3:::${var.s3_bucket_name}/weather/*",
          "arn:aws:s3:::${var.s3_bucket_name}/raw/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = "*"
      }
    ]
  })
}

#### Fetch Weather Lambda (Outside VPC - Has Internet) ####
resource "aws_lambda_function" "fetch_weather" {
  function_name = "cyclelink-${var.environment}-fetch-weather"
  description   = "Fetches real-time weather data (sitting outside VPC for internet access)"

  role    = aws_iam_role.lambda_exec.arn
  handler = "handler.lambda_handler"
  runtime = "python3.12"
  timeout = 30

  filename         = data.archive_file.fetch_weather_zip.output_path
  source_code_hash = data.archive_file.fetch_weather_zip.output_base64sha256

  environment {
    variables = {
      S3_BUCKET_NAME      = var.s3_bucket_name
      PUSH_WEATHER_LAMBDA = "cyclelink-${var.environment}-push-data-to-cache"
    }
  }
}

#### Push Data to Cache Lambda (Inside VPC - Has Cache Access) ####
resource "aws_lambda_function" "push_data_to_cache" {
  function_name = "cyclelink-${var.environment}-push-data-to-cache"
  description   = "Pushes weather data to ElastiCache (sitting inside VPC)"

  role    = aws_iam_role.lambda_exec.arn
  handler = "handler.pusher_handler"
  runtime = "python3.12"
  timeout = 30

  filename         = data.archive_file.push_data_to_cache_zip.output_path
  source_code_hash = data.archive_file.push_data_to_cache_zip.output_base64sha256

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = [var.security_group_id]
  }

  environment {
    variables = {
      ELASTICACHE_ENDPOINT = var.elasticache_endpoint
      ELASTICACHE_PORT     = var.elasticache_port
    }
  }
}

#### Scheduled Trigger ####
resource "aws_cloudwatch_event_rule" "fetch_weather_schedule" {
  count = var.enable_weather_schedule ? 1 : 0

  name                = "cyclelink-${var.environment}-fetch-weather-schedule"
  description         = "Trigger fetch_weather Lambda every 5 minutes"
  schedule_expression = var.weather_schedule_expression
}

resource "aws_cloudwatch_event_target" "fetch_weather_target" {
  count = var.enable_weather_schedule ? 1 : 0

  rule = aws_cloudwatch_event_rule.fetch_weather_schedule[0].name
  arn  = aws_lambda_function.fetch_weather.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  count = var.enable_weather_schedule ? 1 : 0

  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fetch_weather.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.fetch_weather_schedule[0].arn
}
