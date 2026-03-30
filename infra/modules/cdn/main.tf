data "aws_cloudfront_cache_policy" "use_origin" {
  name = "UseOriginCacheControlHeaders-QueryStrings"
}
data "aws_cloudfront_origin_request_policy" "all_headers" {
  name = "Managed-AllViewerExceptHostHeader"
}

############################################################
# CloudFront Distribution
############################################################
resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled    = true
  comment             = "CloudFront for ${var.environment} ALB"
  price_class         = "PriceClass_100"

  origin {
    domain_name = var.alb_dns_name
    origin_id   = "ALB-Origin"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    custom_header {
      name  = "X-Custom-Header"
      value = var.cloudfront_header_secret
    }
  }

  default_cache_behavior {
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "ALB-Origin"

    cache_policy_id          = data.aws_cloudfront_cache_policy.use_origin.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_headers.id

    viewer_protocol_policy = "redirect-to-https"
  }


  restrictions {
    geo_restriction {
      restriction_type = "whitelist"
      locations        = ["SG"]
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Environment = var.environment
  }
}
