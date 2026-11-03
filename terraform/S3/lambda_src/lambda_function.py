import io
import os
import urllib.parse
import boto3
from PIL import Image, ImageOps

s3_client = boto3.client("s3")

# Kích thước ảnh xuất xưởng
IMAGE_SPECS = {
    "thumbnails": (300, 300),
    "details": (1080, 1080)
}

def lambda_handler(event, context):
    """
    AWS Lambda Handler - Xử lý tối ưu ảnh tự động theo kiến trúc Event-Driven:
    1. Nhận sự kiện PutObject từ thư mục 'uploads/' trên S3.
    2. Tải ảnh gốc về RAM của Lambda.
    3. Dùng Pillow chuẩn hóa hướng ảnh (EXIF), nén sang WebP độ nét cao.
    4. Lưu vào 'processed/thumbnails/' và 'processed/details/'.
    """
    for record in event.get("Records", []):
        bucket_name = record["s3"]["bucket"]["name"]
        raw_key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

        # CHẶN VÒNG LẶP & THƯ MỤC TRỐNG: Chỉ xử lý nếu file bắt đầu bằng 'uploads/' và không phải folder
        if not raw_key.startswith("uploads/") or raw_key.endswith("/"):
            print(f"[SKIP] Bỏ qua file không thuộc uploads/ hoặc là thư mục: {raw_key}")
            continue

        filename = os.path.basename(raw_key)
        base_name, _ = os.path.splitext(filename)
        print(f"[START] Bắt đầu xử lý ảnh: {raw_key} từ bucket {bucket_name}")

        try:
            # 1. Tải ảnh gốc
            response = s3_client.get_object(Bucket=bucket_name, Key=raw_key)
            image_data = response["Body"].read()

            with Image.open(io.BytesIO(image_data)) as img:
                # Sửa góc quay ảnh điện thoại nếu có metadata EXIF
                try:
                    img = ImageOps.exif_transpose(img)
                except Exception as e:
                    print(f"[WARN] Không thể đọc EXIF orientation: {e}")

                # Chuyển đổi hệ màu sang RGB nếu là RGBA (PNG/WebP trong suốt)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # 2. Xử lý từng phiên bản
                for folder_name, (max_w, max_h) in IMAGE_SPECS.items():
                    resized_img = img.copy()
                    resized_img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

                    buffer = io.BytesIO()
                    resized_img.save(buffer, format="WEBP", quality=85, optimize=True)
                    buffer.seek(0)

                    target_key = f"processed/{folder_name}/{base_name}.webp"

                    # 3. Ghi kết quả vào thư mục processed/
                    s3_client.put_object(
                        Bucket=bucket_name,
                        Key=target_key,
                        Body=buffer,
                        ContentType="image/webp",
                        CacheControl="public, max-age=31536000, immutable" # Cache 1 năm trên Browser/CDN
                    )
                    print(f"[DONE] Đã tạo thành công: {target_key}")

        except Exception as err:
            print(f"[ERROR] Lỗi khi xử lý {raw_key}: {str(err)}")
            raise err

    return {"status": "SUCCESS"}

