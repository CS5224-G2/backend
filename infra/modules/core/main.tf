# This is the core module that will be deployed to both dev and prod environments.
# To add a resource (like an S3 bucket or RDS database), define it here.

resource "aws_s3_bucket" "cyclelink_s3_bucket" {
  bucket = "cyclelink-${var.environment}-s3-bucket" 
}
