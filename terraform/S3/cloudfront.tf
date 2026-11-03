# ==============================================================================
# AMAZON CLOUDFRONT CDN (TÙY CHỌN - KHI var.enable_cloudfront = true)
# ==============================================================================

# 1. ORIGIN ACCESS CONTROL (OAC) - CHUẨN BẢO MẬT MỚI NHẤT CỦA AWS
# Cho phép CloudFront đọc S3 mà không cần mở public S3 Bucket
resource "aws_cloudfront_origin_access_control" "oac" {
  count                             = var.enable_cloudfront ? 1 : 0
  name                              = "${var.project_name}-s3-oac-${var.environment}"
  description                       = "OAC cho phep CloudFront doc anh tu Media S3 Bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# 2. CLOUDFRONT DISTRIBUTION
resource "aws_cloudfront_distribution" "media_cdn" {
  count   = var.enable_cloudfront ? 1 : 0
  enabled = true
  comment = "UniMarket CDN phan phoi anh san pham va avatar"

  origin {
    domain_name              = aws_s3_bucket.media.bucket_regional_domain_name
    origin_id                = "S3-${aws_s3_bucket.media.id}"
    origin_access_control_id = aws_cloudfront_origin_access_control.oac[0].id
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.media.id}"

    # Tự động chuyển HTTP sang HTTPS an toàn
    viewer_protocol_policy = "redirect-to-https"

    # Sử dụng AWS Managed Cache Policy: CachingOptimized (ID: 658327ea-f89d-4fab-a63d-7e88639e58f6)
    # Tự động nén Gzip và Brotli, cache tại Edge Servers gần người dùng
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"

    # Sử dụng AWS Managed Response Headers Policy: CORS-and-SecurityHeaders
    response_headers_policy_id = "e613b803-37e8-42c5-ae9e-c6c73572270b"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none" # Không giới hạn quốc gia
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  price_class = "PriceClass_200" # Phủ sóng Edge Location Châu Á (có Việt Nam)
}

# 3. CẬP NHẬT BUCKET POLICY CHO PHÉP CLOUDFRONT OAC ĐỌC DỮ LIỆU TỪ S3
resource "aws_s3_bucket_policy" "allow_cloudfront_oac" {
  count  = var.enable_cloudfront ? 1 : 0
  bucket = aws_s3_bucket.media.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontServicePrincipalReadOnly"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.media.arn}/processed/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.media_cdn[0].arn
          }
        }
      }
    ]
  })
}

