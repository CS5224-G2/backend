#### Lambda Packaging ####

resource "null_resource" "install_dependencies" {
  provisioner "local-exec" {
    command = <<EOT
      set -e
      rm -rf ${path.module}/build/package
      mkdir -p ${path.module}/build/package
      python3 -m pip install -r ${path.module}/../../../scripts/lambda/fetch_weather/requirements.txt -t ${path.module}/build/package
      cp ${path.module}/../../../scripts/lambda/fetch_weather/handler.py ${path.module}/build/package/
    EOT
  }

  triggers = {
    # Added version suffix to force a re-run for this fix
    build_config_v2  = "python3-pip-v2"
    handler_hash      = filemd5("${path.module}/../../../scripts/lambda/fetch_weather/handler.py")
    requirements_hash = filemd5("${path.module}/../../../scripts/lambda/fetch_weather/requirements.txt")
  }
}

data "archive_file" "fetch_weather" {
  type        = "zip"
  source_dir  = "${path.module}/build/package"
  output_path = "${path.module}/build/fetch_weather.zip"

  depends_on = [null_resource.install_dependencies]
}
