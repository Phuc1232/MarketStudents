from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import List, Optional
from sqlalchemy.orm import Session
from src.api.deps import get_db
from src.modules.User.service import get_current_user
from src.modules import User, StudentVerification
from src.share.s3_service import storage_service
from sqlalchemy import select
from pydantic import BaseModel, Field
from uuid import UUID
from starlette.concurrency import run_in_threadpool
from src.share.media_uploads import ensure_available, register_upload, inspect_upload

router = APIRouter(
    prefix="/upload",
    tags=["Upload & Media"],
    dependencies=[Depends(get_current_user)]
)


# ==============================================================================
# 1. UPLOAD ẢNH CÔNG KHAI (PUBLIC MEDIA: AVATAR / ẢNH SẢN PHẨM ĐƠN)
# ==============================================================================
@router.post("/image", status_code=status.HTTP_201_CREATED)
async def upload_single_image(
    file: UploadFile = File(..., description="File ảnh đơn lẻ (.jpg, .png, .webp, tối đa 10MB)"),
    user: User = Depends(get_current_user)
):

    result = await storage_service.upload_media_image(file)
    return {
        "message": "Tải ảnh lên thành công",
        **result
    }


@router.post("/images", status_code=status.HTTP_201_CREATED)
async def upload_multiple_images(
    files: List[UploadFile] = File(..., description="Danh sách từ 1 đến 5 file ảnh sản phẩm"),
    user: User = Depends(get_current_user)
):
    if not 1 <= len(files) <= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mỗi sản phẩm chỉ được tải lên tối đa 5 hình ảnh!"
        )

    await run_in_threadpool(ensure_available)
    uploaded_images = []
    for file in files:
        res = await storage_service.upload_media_image(file)
        await run_in_threadpool(register_upload, user.id, res)
        uploaded_images.append({
            "image_url": res["raw_url"],
            "thumbnail_url": res["thumbnail_url"],
            "detail_url": res["detail_url"],
            "raw_url": res["raw_url"],
            "file_id": res["file_id"],
            "status": "processing" if res["storage"] == "S3" else "ready"
        })

    return {
        "message": f"Đã tải lên thành công {len(uploaded_images)} ảnh",
        "count": len(uploaded_images),
        "images": uploaded_images
    }


class ImageStatusRequest(BaseModel):
    file_ids: List[UUID] = Field(min_length=1, max_length=5)


@router.post("/images/status")
def image_status(body: ImageStatusRequest, user: User = Depends(get_current_user)):
    # Report failures per image so a single expired upload does not hide the others.
    images = []
    for file_id in body.file_ids:
        try:
            images.append(inspect_upload(str(file_id), user.id))
        except HTTPException as exc:
            images.append({"file_id": str(file_id), "status": "error",
                           "error_code": exc.status_code, "message": exc.detail})
    return {"images": images}


@router.post("/private-document", status_code=status.HTTP_201_CREATED)
async def upload_private_document_file(
    file: UploadFile = File(..., description="Tệp tài liệu riêng tư (.jpg, .png, .pdf, tối đa 10MB)"),
    user: User = Depends(get_current_user)
):

    res = await storage_service.upload_private_document(file)
    return {
        "message": "Tải tài liệu bảo mật lên thành công",
        "doc_key": res["doc_key"],
        "doc_id": res["doc_id"],
        "storage": res["storage"]
    }

@router.get("/student-card/view/{target_user_id}", status_code=status.HTTP_200_OK)
def get_student_card_view_url(
    target_user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    is_admin = getattr(user, "role_id", None) == 1
    if not is_admin and user.id != target_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xem tài liệu xác thực của người dùng khác!"
        )

    # Tìm thông tin thẻ SV trong Database
    stmt = select(StudentVerification).where(StudentVerification.user_id == target_user_id)
    verification = db.scalars(stmt).first()

    if not verification or not verification.student_card_img:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy ảnh thẻ sinh viên cho người dùng này!"
        )

    # Sinh link Pre-signed URL an toàn
    view_url = storage_service.generate_presigned_view_url(verification.student_card_img, expires_in=300)

    return {
        "user_id": target_user_id,
        "view_url": view_url,
        "expires_in_seconds": 300,
        "notice": "Đường dẫn chỉ có hiệu lực trong 5 phút vì lý do bảo mật thông tin cá nhân."
    }
