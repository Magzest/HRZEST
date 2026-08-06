resource "aws_s3_bucket" "hrms_storage" {
  bucket = "${var.project_name}-storage-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-storage"
  }
}

resource "aws_s3_bucket_public_access_block" "hrms_storage_pab" {
  bucket                  = aws_s3_bucket.hrms_storage.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "hrms_storage_lifecycle" {
  bucket = aws_s3_bucket.hrms_storage.id

  rule {
    id     = "purge-garbage"
    status = "Enabled"
    filter {
      prefix = "garbage/"
    }
    expiration {
      days = 30
    }
  }

  rule {
    id     = "purge-cache"
    status = "Enabled"
    filter {
      prefix = "cache/"
    }
    expiration {
      days = 30
    }
  }
}
