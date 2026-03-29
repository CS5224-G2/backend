#### Lambda Packaging ####

# --- Build for Fetch-Weather (Outside VPC) ---
resource "null_resource" "install_fetcher_deps" {
  provisioner "local-exec" {
    command = <<EOT
      set -e
      rm -rf ${path.module}/build/fetch-weather
      mkdir -p ${path.module}/build/fetch-weather
      cp ${path.module}/../../../scripts/lambda/fetch-weather/handler.py ${path.module}/build/fetch-weather/
    EOT
  }

  triggers = {
    build_v4          = "v4"
    handler_hash      = filemd5("${path.module}/../../../scripts/lambda/fetch-weather/handler.py")
  }
}

data "archive_file" "fetch_weather_zip" {
  depends_on  = [null_resource.install_fetcher_deps]
  type        = "zip"
  source_dir  = "${path.module}/build/fetch-weather"
  output_path = "${path.module}/build/fetch_weather.zip"
}

# --- Build for Push-Data-to-Cache (Inside VPC) ---
resource "null_resource" "install_pusher_deps" {
  provisioner "local-exec" {
    command = <<EOT
      set -e
      rm -rf ${path.module}/build/push-data-to-cache
      mkdir -p ${path.module}/build/push-data-to-cache
      python3 -m pip install -r ${path.module}/../../../scripts/lambda/push-data-to-cache/requirements.txt -t ${path.module}/build/push-data-to-cache
      cp ${path.module}/../../../scripts/lambda/push-data-to-cache/handler.py ${path.module}/build/push-data-to-cache/
    EOT
  }

  triggers = {
    build_v5          = "v5"
    handler_hash      = filemd5("${path.module}/../../../scripts/lambda/push-data-to-cache/handler.py")
    requirements_hash = filemd5("${path.module}/../../../scripts/lambda/push-data-to-cache/requirements.txt")
  }
}

data "archive_file" "push_data_to_cache_zip" {
  depends_on  = [null_resource.install_pusher_deps]
  type        = "zip"
  source_dir  = "${path.module}/build/push-data-to-cache"
  output_path = "${path.module}/build/push_data_to_cache.zip"
}
