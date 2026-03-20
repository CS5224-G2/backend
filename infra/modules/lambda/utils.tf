#### Lambda Packaging ####
data "archive_file" "fetch_weather" {
  type        = "zip"
  source_dir  = "${path.module}/../../../scripts/lambda/fetch_weather"
  output_path = "${path.module}/build/fetch_weather.zip"
}
