#### Lambda Outputs ####
output "fetch_weather_function_name" {
  value = aws_lambda_function.fetch_weather.function_name
}

output "fetch_weather_function_arn" {
  value = aws_lambda_function.fetch_weather.arn
}

output "lambda_exec_role_arn" {
  value = aws_iam_role.lambda_exec.arn
}
