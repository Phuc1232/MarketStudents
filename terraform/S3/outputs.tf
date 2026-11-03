# ==============================================================================
# GIÁ TRỊ ĐẦU RA (OUTPUTS) ĐỂ ĐIỀN VÀO FILE .ENV CỦA BACKEND VÀ FRONTEND
# ==============================================================================

output "aws_region" {
  description = "Region triển khai"
  value       = var.aws_region
}

output "media_bucket_name" {
  description = "Tên Bucket lưu ảnh sản phẩm (Điền vào S3_MEDIA_BUCKET_NAME trong .env)"
  value       = aws_s3_bucket.media.id
}

output "private_bucket_name" {
  description = "Tên Bucket lưu ảnh thẻ sinh viên bí mật (Điền vào S3_PRIVATE_BUCKET_NAME trong .env)"
  value       = aws_s3_bucket.private_docs.id
}

output "lambda_resizer_name" {
  description = "Tên hàm Lambda tự động resize ảnh"
  value       = aws_lambda_function.image_resizer.function_name
}

output "cloudfront_domain_name" {
  description = "Tên miền CloudFront CDN (nếu bật)"
  value       = var.enable_cloudfront ? aws_cloudfront_distribution.media_cdn[0].domain_name : "CLOUDFRONT_DISABLED"
}

output "media_base_url" {
  description = "Base URL để Frontend và Backend ghép đường dẫn ảnh hiển thị"
  value       = var.enable_cloudfront ? "https://${aws_cloudfront_distribution.media_cdn[0].domain_name}" : "https://${aws_s3_bucket.media.bucket_regional_domain_name}"
}

