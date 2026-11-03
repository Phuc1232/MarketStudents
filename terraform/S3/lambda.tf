# ==============================================================================
# NÉN MÃ NGUỒN PYTHON THÀNH FILE ZIP ĐỂ DEPLOY LÊN AWS LAMBDA
# ==============================================================================
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda_src/lambda_function.py"
  output_path = "${path.module}/lambda_src/lambda_function.zip"
}

# ==============================================================================
# IAM ROLE & POLICIES CHO AWS LAMBDA
# ==============================================================================
resource "aws_iam_role" "lambda_exec" {
  name = "${var.project_name}-image-resizer-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Policy cho phép Lambda ghi log ra CloudWatch
resource "aws_iam_policy" "lambda_logging" {
  name = "${var.project_name}-lambda-logging-${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Policy phân quyền tối thiểu (Least Privilege):
# - Chỉ đọc file từ thư mục uploads/*
# - Chỉ ghi file vào thư mục processed/*
resource "aws_iam_policy" "lambda_s3_access" {
  name = "${var.project_name}-lambda-s3-access-${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadUploadsOnly"
        Action   = ["s3:GetObject"]
        Effect   = "Allow"
        Resource = "${aws_s3_bucket.media.arn}/uploads/*"
      },
      {
        Sid      = "WriteProcessedOnly"
        Action   = ["s3:PutObject"]
        Effect   = "Allow"
        Resource = "${aws_s3_bucket.media.arn}/processed/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_logging" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_logging.arn
}

resource "aws_iam_role_policy_attachment" "attach_s3" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_s3_access.arn
}

# ==============================================================================
# AWS LAMBDA FUNCTION (IMAGE RESIZER)
# ==============================================================================
resource "aws_lambda_function" "image_resizer" {
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  function_name    = "${var.project_name}-image-resizer-${var.environment}"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.11"
  memory_size      = 512 # RAM 512MB để xử lý ảnh nhanh
  timeout          = 20  # Timeout 20s

  # Gắn Layer Pillow để xử lý nén WebP và resize
  layers = [var.pillow_lambda_layer_arn]

  environment {
    variables = {
      ENVIRONMENT = var.environment
    }
  }
}

# Cấp quyền cho dịch vụ S3 được phép kích hoạt (Invoke) hàm Lambda này
resource "aws_lambda_permission" "allow_s3_trigger" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.image_resizer.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.media.arn
}

# ==============================================================================
# S3 EVENT NOTIFICATION (EVENT-DRIVEN TRIGGER)
# ==============================================================================
resource "aws_s3_bucket_notification" "media_upload_trigger" {
  bucket = aws_s3_bucket.media.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.image_resizer.arn
    events              = ["s3:ObjectCreated:*"]

    # QUAN TRỌNG: Chỉ kích hoạt khi file nằm trong thư mục 'uploads/'
    # Ngăn chặn hoàn toàn lỗi lặp vô tận (Infinite Recursive Loop)
    filter_prefix = "uploads/"
  }

  depends_on = [aws_lambda_permission.allow_s3_trigger]
}

