from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.modules import User, AppealCreateRequest, MyAppelStatusResponse
from .services import get_current_banned_user, submit_identity_appeal, get_my_latest_appeal

router = APIRouter(
    prefix="/identity-verification",
    tags=["Identity Verification & Appeal"]
)


@router.post(
    "/appeal",
    response_model=MyAppelStatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Nộp hồ sơ kháng cáo CCCD & SIM chính chủ xin mở khóa tài khoản (Banned User)"
)
def create_appeal(
    payload: AppealCreateRequest,
    current_banned_user: User = Depends(get_current_banned_user),
    db: Session = Depends(get_db)
):
    """
    Quy trình kháng cáo danh tính mở khóa tài khoản (Sequence 6 SRS):
    - Dành riêng cho tài khoản đang bị khóa (`isActive = False`).
    - Nộp thông tin liên hệ, ảnh 2 mặt CCCD và ảnh tra cứu SIM chính chủ (1414).
    - Ngăn chặn nộp trùng nếu đang có đơn PENDING chưa xử lý.
    """
    return submit_identity_appeal(
        payload=payload,
        current_banned_user=current_banned_user,
        db=db
    )


@router.get(
    "/my-appeal",
    response_model=MyAppelStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Tra cứu tình trạng hồ sơ kháng cáo gần nhất (Banned User)"
)
def check_my_appeal_status(
    current_banned_user: User = Depends(get_current_banned_user),
    db: Session = Depends(get_db)
):
    """Xem tiến độ thẩm định của Ban Quản Trị đối với đơn kháng cáo của chính mình."""
    return get_my_latest_appeal(
        current_banned_user=current_banned_user,
        db=db
    )
