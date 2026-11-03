variable "aws_region" {
  description = "AWS Region deploy hạ tầng (mặc định Singapore để latency thấp về Việt Nam)"
  type        = string
  default     = "ap-southeast-1"
}

variable "environment" {
  description = "Môi trường triển khai (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Tên dự án"
  type        = string
  default     = "unimarket"
}

variable "media_bucket_name" {
  description = "Tên Bucket lưu ảnh sản phẩm & avatar công khai (để trống sẽ tự sinh theo project và environment)"
  type        = string
  default     = ""
}

variable "private_bucket_name" {
  description = "Tên Bucket lưu tài liệu nhạy cảm (thẻ SV, căn cước) bị khóa truy cập công khai"
  type        = string
  default     = ""
}

variable "enable_cloudfront" {
  description = "Bật hoặc tắt CDN CloudFront (True = bật CDN tăng tốc ảnh, False = chỉ dùng S3 trực tiếp)"
  type        = bool
  default     = true
}

variable "pillow_lambda_layer_arn" {
  description = "ARN của Lambda Layer Pillow (Xử lý ảnh Python 3.11 trên region Singapore ap-southeast-1)"
  type        = string
  default     = "arn:aws:lambda:ap-southeast-1:770693421928:layer:Klayers-p311-Pillow:11"
}

