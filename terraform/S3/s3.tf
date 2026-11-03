# Sinh chuỗi ngẫu nhiên 4 bytes để đảm bảo tên Bucket không bị trùng lặp trên toàn cầu của AWS
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

locals {
  media_bucket_name   = var.media_bucket_name != "" ? var.media_bucket_name : "${var.project_name}-media-${var.environment}-${random_id.bucket_suffix.hex}"
  private_bucket_name = var.private_bucket_name != "" ? var.private_bucket_name : "${var.project_name}-private-docs-${var.environment}-${random_id.bucket_suffix.hex}"
}

# ==============================================================================
# 1. BUCKET MEDIA CÔNG KHAI (Lưu ảnh sản phẩm, ảnh đại diện)
# ==============================================================================
resource "aws_s3_bucket" "media" {
  bucket        = local.media_bucket_name
  force_destroy = true # Cho phép xóa bucket khi destroy môi trường dev
}

# Bật mã hóa phía máy chủ (Server-Side Encryption) mặc định
resource "aws_s3_bucket_server_side_encryption_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Cấu hình CORS để Frontend (Web/Mobile) có thể tải ảnh và upload trực tiếp mượt mà
resource "aws_s3_bucket_cors_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD", "PUT", "POST"]
    allowed_origins = ["*"] # Trong môi trường Prod có thể giới hạn về domain frontend
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
}

# Quản lý quyền truy cập công khai của Media Bucket
resource "aws_s3_bucket_public_access_block" "media" {
  bucket = aws_s3_bucket.media.id

  # Nếu dùng CloudFront: Khóa chặt S3 (Block Public = true), chỉ cho CloudFront đọc qua OAC
  # Nếu không dùng CloudFront: Mở quyền để client có thể đọc ảnh public trực tiếp từ S3
  block_public_acls       = var.enable_cloudfront
  block_public_policy     = var.enable_cloudfront
  ignore_public_acls      = var.enable_cloudfront
  restrict_public_buckets = var.enable_cloudfront
}

# Policy cho phép đọc công khai thư mục processed/* khi KHÔNG sử dụng CloudFront
resource "aws_s3_bucket_policy" "media_public_read" {
  count  = var.enable_cloudfront ? 0 : 1
  bucket = aws_s3_bucket.media.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadProcessedOnly"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.media.arn}/processed/*"
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.media]
}

# ==============================================================================
# 2. BUCKET PRIVATE BẢO MẬT (Lưu ảnh thẻ sinh viên, căn cước - CẤM PUBLIC)
# ==============================================================================
resource "aws_s3_bucket" "private_docs" {
  bucket        = local.private_bucket_name
  force_destroy = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "private_docs" {
  bucket = aws_s3_bucket.private_docs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# KHÓA KÍN 100%: Chặn mọi truy cập trực tiếp từ Internet (Bắt buộc dùng Pre-signed URL)
resource "aws_s3_bucket_public_access_block" "private_docs" {
  bucket = aws_s3_bucket.private_docs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

