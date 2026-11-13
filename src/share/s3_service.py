import os
import uuid
import logging
import io
import warnings
from PIL import Image, UnidentifiedImageError
from typing import Tuple, Dict, Any, Optional
from fastapi import HTTPException, status, UploadFile
from starlette.concurrency import run_in_threadpool
from src.Core.config import (
    AWS_REGION,
    S3_MEDIA_BUCKET,
    S3_PRIVATE_DOCS_BUCKET,
    MEDIA_BASE_URL,
    UPLOAD_MAX_FILE_SIZE_MB,
    APP_ENV,
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
                raise RuntimeError("Cannot initialize configured S3 storage") from e

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
        extensions = {"jpg", "jpeg", "png", "webp"}
        if "application/pdf" in allowed_types:
            extensions.add("pdf")
        if ext not in extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Phần mở rộng '.{ext}' không hợp lệ!"
            )

        return ext

    @staticmethod
    def validate_image_bytes(content: bytes, content_type: str):
        formats = {"image/jpeg": "JPEG", "image/jpg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(content)) as image:
                    if image.format != formats.get(content_type) or image.width * image.height > 24_000_000:
                        raise ValueError("Invalid image format or excessive dimensions")
                    image.verify()
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
                Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            raise HTTPException(422, "Ảnh không hợp lệ hoặc vượt quá 24 triệu pixel.") from exc

    @staticmethod
    def validate_document_bytes(content: bytes, ext: str, content_type: str):
        """Xác thực định dạng nội dung byte cho tài liệu PDF hoặc hình ảnh."""
        if ext == "pdf" or content_type == "application/pdf":
            if not content.startswith(b"%PDF-"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Tệp PDF không hợp lệ hoặc bị hỏng."
                )
        else:
            StorageService.validate_image_bytes(content, content_type)

    async def upload_media_image(self, file: UploadFile) -> Dict[str, Any]:
        """
        Upload ảnh sản phẩm hoặc avatar công khai.
        - Khi có S3: Đẩy vào S3_MEDIA_BUCKET với key 'uploads/{uuid}.{ext}'.
          Lambda Event-Driven sẽ tự động nén thành WebP tại 'processed/thumbnails/' và 'processed/details/'.
        - Khi ở Local dev: Lưu vào static/uploads/media/.
        """
        ext = self.validate_file(file, ALLOWED_IMAGE_TYPES)
        file_bytes = await file.read(UPLOAD_MAX_FILE_SIZE_MB * 1024 * 1024 + 1)

        # Kiểm tra dung lượng
        max_bytes = UPLOAD_MAX_FILE_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Dung lượng file vượt quá giới hạn cho phép ({UPLOAD_MAX_FILE_SIZE_MB}MB)!"
            )

        await run_in_threadpool(self.validate_image_bytes, file_bytes, file.content_type)
        file_id = str(uuid.uuid4())
        filename = f"{file_id}.{ext}"

        if self.use_s3 and self.s3_client:
            s3_key = f"uploads/{filename}"
            try:
                await run_in_threadpool(self.s3_client.put_object,
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
                    "image_url": raw_url,
                    "thumbnail_url": thumbnail_url,
                    "detail_url": detail_url,
                    "raw_url": raw_url,
                    "storage": "S3"
                }
            except Exception as e:
                logger.exception("[STORAGE] S3 media upload failed")
                raise HTTPException(503, "Không tải được ảnh lên S3. Vui lòng thử lại.") from e

        # --- LOCAL FALLBACK ---
        if APP_ENV in {"production", "prod"}:
            raise HTTPException(503, "Production yêu cầu cấu hình S3 cho ảnh.")
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
        file_bytes = await file.read(UPLOAD_MAX_FILE_SIZE_MB * 1024 * 1024 + 1)

        max_bytes = UPLOAD_MAX_FILE_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Dung lượng file vượt quá giới hạn ({UPLOAD_MAX_FILE_SIZE_MB}MB)!"
            )

        await run_in_threadpool(self.validate_document_bytes, file_bytes, ext, file.content_type)

        doc_id = str(uuid.uuid4())
        filename = f"{doc_id}.{ext}"

        if self.use_s3 and self.s3_client and S3_PRIVATE_DOCS_BUCKET:
            s3_key = f"verifications/{filename}"
            try:
                await run_in_threadpool(self.s3_client.put_object,
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
                logger.exception("[STORAGE] S3 private upload failed")
                raise HTTPException(503, "Không tải được tài liệu lên S3.") from e

        # --- LOCAL FALLBACK ---
        if APP_ENV in {"production", "prod"} or self.use_s3:
            raise HTTPException(503, "Cần cấu hình S3 private cho tài liệu.")
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
                raise HTTPException(503, "Không tạo được liên kết xem tài liệu.") from e

        # Local fallback view URL
        if APP_ENV in {"production", "prod"} or self.use_s3:
            raise HTTPException(503, "Dịch vụ tài liệu riêng tư chưa sẵn sàng.")
        clean_name = os.path.basename(doc_key)
        return f"/static/uploads/private/{clean_name}"

    def delete_s3_media_objects(self, keys: list[str]) -> bool:
        """Xóa danh sách objects khỏi S3 Media Bucket (processed/thumbnails, processed/details, uploads)."""
        if not self.use_s3 or not self.s3_client or not S3_MEDIA_BUCKET or not keys:
            return False
        try:
            delete_objects = [{"Key": k.lstrip("/")} for k in keys if k]
            if delete_objects:
                self.s3_client.delete_objects(
                    Bucket=S3_MEDIA_BUCKET,
                    Delete={"Objects": delete_objects, "Quiet": True}
                )
                logger.info(f"[STORAGE] Deleted {len(delete_objects)} objects from S3 media bucket: {keys}")
                return True
        except Exception as e:
            logger.warning(f"[STORAGE] Failed to delete S3 objects {keys}: {e}")
        return False


# Singleton Instance
storage_service = StorageService()

