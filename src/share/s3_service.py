import os
import uuid
import logging
from typing import Tuple, Dict, Any, Optional
from fastapi import HTTPException, status, UploadFile
from src.Core.config import (
    AWS_REGION,
    S3_MEDIA_BUCKET,
    S3_PRIVATE_DOCS_BUCKET,
    MEDIA_BASE_URL,
    UPLOAD_MAX_FILE_SIZE_MB,
)

logger = logging.getLogger("unimarket.storage")

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/jpg",
}

ALLOWED_DOC_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/jpg",
    "application/pdf",
}

LOCAL_UPLOAD_DIR = os.path.join("static", "uploads")
LOCAL_MEDIA_DIR = os.path.join(LOCAL_UPLOAD_DIR, "media")
LOCAL_PRIVATE_DIR = os.path.join(LOCAL_UPLOAD_DIR, "private")


class StorageService:
    def __init__(self):
        self.use_s3 = bool(S3_MEDIA_BUCKET)
        self.s3_client = None

        if self.use_s3:
            try:
                import boto3
                self.s3_client = boto3.client("s3", region_name=AWS_REGION)
                logger.info(f"[STORAGE] Connected to AWS S3 (Bucket: {S3_MEDIA_BUCKET}, Region: {AWS_REGION})")
            except Exception as e:
                logger.warning(f"[STORAGE] Failed to initialize S3 client: {e}. Falling back to Local Storage.")
                self.use_s3 = False

        if not self.use_s3:
            # Ensure local fallback directories exist
            os.makedirs(LOCAL_MEDIA_DIR, exist_ok=True)
            os.makedirs(LOCAL_PRIVATE_DIR, exist_ok=True)
            logger.info(f"[STORAGE] Running in LOCAL FALLBACK mode (Directory: {LOCAL_UPLOAD_DIR})")

    @property
    def is_s3_active(self) -> bool:
        return self.use_s3

    def validate_file(self, file: UploadFile, allowed_types: set, max_mb: int = UPLOAD_MAX_FILE_SIZE_MB) -> str:
        """Kiểm tra định dạng và phần mở rộng file hợp lệ"""
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên file không hợp lệ!"
            )

        # Kiểm tra Content-Type
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Định dạng file '{file.content_type}' không được hỗ trợ! Chỉ chấp nhận: {', '.join(allowed_types)}"
            )

        # Lấy đuôi mở rộng
        ext = file.filename.split(".")[-1].lower()
        if ext not in ["jpg", "jpeg", "png", "webp", "pdf"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Phần mở rộng '.{ext}' không hợp lệ!"
            )

        return ext

    async def upload_media_image(self, file: UploadFile) -> Dict[str, Any]:
        """
        Upload ảnh sản phẩm hoặc avatar công khai.
        - Khi có S3: Đẩy vào S3_MEDIA_BUCKET với key 'uploads/{uuid}.{ext}'.
          Lambda Event-Driven sẽ tự động nén thành WebP tại 'processed/thumbnails/' và 'processed/details/'.
        - Khi ở Local dev: Lưu vào static/uploads/media/.
        """
        ext = self.validate_file(file, ALLOWED_IMAGE_TYPES)
        file_bytes = await file.read()

        # Kiểm tra dung lượng
        max_bytes = UPLOAD_MAX_FILE_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Dung lượng file vượt quá giới hạn cho phép ({UPLOAD_MAX_FILE_SIZE_MB}MB)!"
            )

        file_id = str(uuid.uuid4())
        filename = f"{file_id}.{ext}"

        if self.use_s3 and self.s3_client:
            s3_key = f"uploads/{filename}"
            try:
                self.s3_client.put_object(
                    Bucket=S3_MEDIA_BUCKET,
                    Key=s3_key,
                    Body=file_bytes,
                    ContentType=file.content_type,
                )
                logger.info(f"[STORAGE] Uploaded to S3: s3://{S3_MEDIA_BUCKET}/{s3_key}")

                # Định danh URL tối ưu qua CloudFront (hoặc trực tiếp qua S3 nếu chưa có CloudFront)
                if MEDIA_BASE_URL:
                    base = MEDIA_BASE_URL
                else:
                    base = f"https://{S3_MEDIA_BUCKET}.s3.{AWS_REGION}.amazonaws.com"

                # Link WebP chuẩn hóa mà Lambda sẽ tạo ra
                thumbnail_url = f"{base}/processed/thumbnails/{file_id}.webp"
                detail_url = f"{base}/processed/details/{file_id}.webp"
                raw_url = f"{base}/{s3_key}"

                return {
                    "file_id": file_id,
                    "image_url": thumbnail_url,
                    "thumbnail_url": thumbnail_url,
                    "detail_url": detail_url,
                    "raw_url": raw_url,
                    "storage": "S3"
                }
            except Exception as e:
                logger.error(f"[STORAGE] S3 upload error: {e}. Falling back to local storage.")
                # Fallback to local on error

        # --- LOCAL FALLBACK ---
        local_path = os.path.join(LOCAL_MEDIA_DIR, filename)
        with open(local_path, "wb") as f:
            f.write(file_bytes)

        local_url = f"/static/uploads/media/{filename}"
        return {
            "file_id": file_id,
            "image_url": local_url,
            "thumbnail_url": local_url,
            "detail_url": local_url,
            "raw_url": local_url,
            "storage": "Local"
        }

    async def upload_private_document(self, file: UploadFile) -> Dict[str, Any]:
        """
        Upload tài liệu nhạy cảm (Ảnh thẻ sinh viên, CCCD).
        - Khi có S3: Lưu vào S3_PRIVATE_DOCS_BUCKET với key 'verifications/{uuid}.{ext}' (khóa kín 100%).
        - Khi ở Local dev: Lưu vào static/uploads/private/.
        """
        ext = self.validate_file(file, ALLOWED_DOC_TYPES)
        file_bytes = await file.read()

        max_bytes = UPLOAD_MAX_FILE_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Dung lượng file vượt quá giới hạn ({UPLOAD_MAX_FILE_SIZE_MB}MB)!"
            )

        doc_id = str(uuid.uuid4())
        filename = f"{doc_id}.{ext}"

        if self.use_s3 and self.s3_client and S3_PRIVATE_DOCS_BUCKET:
            s3_key = f"verifications/{filename}"
            try:
                self.s3_client.put_object(
                    Bucket=S3_PRIVATE_DOCS_BUCKET,
                    Key=s3_key,
                    Body=file_bytes,
                    ContentType=file.content_type,
                    ServerSideEncryption="AES256"
                )
                logger.info(f"[STORAGE] Uploaded private doc to S3: s3://{S3_PRIVATE_DOCS_BUCKET}/{s3_key}")
                return {
                    "doc_key": s3_key,
                    "doc_id": doc_id,
                    "storage": "S3"
                }
            except Exception as e:
                logger.error(f"[STORAGE] S3 private upload error: {e}. Falling back to local.")

        # --- LOCAL FALLBACK ---
        local_path = os.path.join(LOCAL_PRIVATE_DIR, filename)
        with open(local_path, "wb") as f:
            f.write(file_bytes)

        local_key = f"local-private/{filename}"
        return {
            "doc_key": local_key,
            "doc_id": doc_id,
            "storage": "Local"
        }

    def generate_presigned_view_url(self, doc_key: str, expires_in: int = 300) -> str:
        """
        Tạo đường link Pre-signed URL xem ảnh thẻ sinh viên bảo mật (mặc định sống 5 phút).
        """
        if self.use_s3 and self.s3_client and S3_PRIVATE_DOCS_BUCKET:
            try:
                presigned_url = self.s3_client.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={
                        "Bucket": S3_PRIVATE_DOCS_BUCKET,
                        "Key": doc_key,
                    },
                    ExpiresIn=expires_in
                )
                return presigned_url
            except Exception as e:
                logger.error(f"[STORAGE] Failed to generate presigned URL: {e}")

        # Local fallback view URL
        clean_name = os.path.basename(doc_key)
        return f"/static/uploads/private/{clean_name}"


# Singleton Instance
storage_service = StorageService()

