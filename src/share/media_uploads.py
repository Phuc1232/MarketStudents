"""Temporary upload ownership in Redis; no database schema changes."""
import json
from uuid import UUID

import redis
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

from src.Core.config import REDIS_URL, S3_MEDIA_BUCKET
from src.share.s3_service import storage_service

UPLOAD_TTL = 24 * 60 * 60


def client():
    if not REDIS_URL:
        raise HTTPException(503, "Cần cấu hình Redis để xác minh ảnh sản phẩm.")
    return redis.Redis.from_url(
        REDIS_URL, decode_responses=True, socket_connect_timeout=3, socket_timeout=3
    )


def ensure_available():
    try:
        client().ping()
    except redis.RedisError as exc:
        raise HTTPException(503, "Không kết nối được dịch vụ quản lý ảnh.") from exc


def register_upload(owner_id: int, result: dict):
    payload = {**result, "owner_id": owner_id}
    try:
        client().setex(f"media-upload:{result['file_id']}", UPLOAD_TTL, json.dumps(payload))
    except redis.RedisError as exc:
        raise HTTPException(503, "Không lưu được lượt upload. Vui lòng thử lại.") from exc


def inspect_upload(file_id: str, owner_id: int) -> dict:
    file_id = str(UUID(str(file_id)))
    try:
        raw = client().get(f"media-upload:{file_id}")
    except redis.RedisError as exc:
        raise HTTPException(503, "Không kết nối được dịch vụ quản lý ảnh.") from exc
    if not raw:
        raise HTTPException(410, "Lượt upload đã hết hạn. Vui lòng tải lại ảnh.")
    data = json.loads(raw)
    if data["owner_id"] != owner_id:
        raise HTTPException(403, "Bạn không có quyền sử dụng ảnh này.")

    # Nếu Redis đã lưu trạng thái ready thì không cần kiểm tra lại trên S3
    if data.get("status") == "ready":
        return {
            "file_id": file_id,
            "thumbnail_url": data["thumbnail_url"],
            "detail_url": data["detail_url"],
            "status": "ready",
        }

    ready = True
    if data["storage"] == "S3":
        if not storage_service.s3_client or not S3_MEDIA_BUCKET:
            raise HTTPException(503, "Dịch vụ lưu trữ ảnh chưa sẵn sàng.")
        for folder in ("thumbnails", "details"):
            try:
                storage_service.s3_client.head_object(
                    Bucket=S3_MEDIA_BUCKET, Key=f"processed/{folder}/{file_id}.webp"
                )
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                if code in {"404", "NoSuchKey", "NotFound"}:
                    ready = False
                else:
                    # 403 can also hide a missing key: do not silently treat it as pending.
                    raise HTTPException(503, "Không kiểm tra được ảnh trên S3. Kiểm tra quyền truy cập.") from exc
            except BotoCoreError as exc:
                raise HTTPException(503, "Không kết nối được S3 để kiểm tra ảnh.") from exc

    # Lưu lại trạng thái ready vào Redis để tối ưu các lần poll sau
    if ready and data.get("status") != "ready":
        data["status"] = "ready"
        try:
            ttl_val = client().ttl(f"media-upload:{file_id}")
            ttl = int(ttl_val) if isinstance(ttl_val, (int, float)) and ttl_val > 0 else UPLOAD_TTL
            client().setex(f"media-upload:{file_id}", ttl, json.dumps(data))
        except (redis.RedisError, TypeError, ValueError):
            pass
    return {
        "file_id": file_id,
        "thumbnail_url": data["thumbnail_url"],
        "detail_url": data["detail_url"],
        "status": "ready" if ready else "processing",
    }


def resolve_product_images(file_ids: list[str], owner_id: int) -> list[dict]:
    if len(set(file_ids)) != len(file_ids):
        raise HTTPException(422, "Danh sách ảnh bị trùng.")
    images = [inspect_upload(file_id, owner_id) for file_id in file_ids]
    if any(image["status"] != "ready" for image in images):
        raise HTTPException(409, "Ảnh chưa xử lý xong. Vui lòng chờ rồi thử lại.")
    return images
