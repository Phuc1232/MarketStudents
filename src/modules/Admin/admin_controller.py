from fastapi import APIRouter, Depends, status, Query, Path
from sqlalchemy.orm import Session
from typing import Optional

from src.api.deps import get_db
from src.modules import (
    User,
    ProductApproveResponse, ProductRejectRequest, ProductRejectResponse,
    AdminProductDetailResponse, PaginatedAdminProductsResponse,
    ReportResolveRequest, ReportResolveResponse, ReportDismissRequest, ReportDismissResponse,
    AdminReportDetailResponse, PaginatedAdminReportsResponse
)
from .services import (
    get_current_staff_or_admin,
    get_current_admin,
    get_pending_products,
    get_admin_product_detail,
    approve_product,
    reject_product,
    admin_delete_product,
    get_admin_reports_list,
    get_admin_report_detail,
    resolve_user_report,
    dismiss_user_report
)

router = APIRouter(
    prefix="/admin",
    tags=["Admin - Moderation"]
)


# ==============================================================================
# 1. KIỂM DUYỆT TIN ĐĂNG (PRODUCT MODERATION - SEQUENCE 12 SRS)
# ==============================================================================

@router.get(
    "/products/pending",
    response_model=PaginatedAdminProductsResponse,
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách tin đăng chờ duyệt (Staff / Admin)"
)
def list_pending_products(
    page: int = Query(1, ge=1, description="Số trang hiện tại"),
    page_size: int = Query(20, ge=1, le=100, description="Số tin mỗi trang"),
    category_id: Optional[int] = Query(None, description="Lọc theo ID danh mục chính"),
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """
    Phục vụ màn hình hàng đợi kiểm duyệt tin đăng dành cho Staff và Admin (Seq 12).
    Lọc toàn bộ sản phẩm có `status_id = 1` (Pending_Approval) và chưa bị xóa mềm.
    """
    return get_pending_products(
        db=db,
        page=page,
        page_size=page_size,
        category_id=category_id
    )


@router.get(
    "/products/{product_id}",
    response_model=AdminProductDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Xem chi tiết tin đăng kiểm duyệt kèm thông tin người bán & EAV (Staff / Admin)"
)
def get_product_detail_for_admin(
    product_id: int = Path(..., ge=1, description="ID tin đăng cần xem xét"),
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """
    Xem toàn diện chi tiết tin đăng phục vụ thẩm định nội dung, hình ảnh, thông số kỹ thuật EAV
    và lịch sử báo cáo vi phạm liên quan.
    """
    return get_admin_product_detail(product_id=product_id, db=db)


@router.patch(
    "/products/{product_id}/approve",
    response_model=ProductApproveResponse,
    status_code=status.HTTP_200_OK,
    summary="Phê duyệt tin đăng sang Active (Staff / Admin)"
)
def approve_pending_product(
    product_id: int = Path(..., ge=1, description="ID tin đăng cần phê duyệt"),
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """
    Phê duyệt tin đăng (Sequence 12 SRS):
    - Chuyển `status_id = 2` (Active) để xuất hiện trên chợ UniMarket.
    - Gửi thông báo chúc mừng vào hộp thư người bán.
    - Ghi nhận Audit Trail vào `SystemLog` (`Approve_Post`).
    """
    return approve_product(
        product_id=product_id,
        current_admin=current_user,
        db=db
    )


@router.patch(
    "/products/{product_id}/reject",
    response_model=ProductRejectResponse,
    status_code=status.HTTP_200_OK,
    summary="Từ chối tin đăng kèm lý do vi phạm (Staff / Admin)"
)
def reject_pending_product(
    product_id: int = Path(..., ge=1, description="ID tin đăng cần từ chối"),
    payload: ProductRejectRequest = ...,
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """
    Từ chối tin đăng vi phạm (Sequence 12 SRS):
    - Chuyển `status_id = 5` (Rejected).
    - Yêu cầu nhập lý do từ chối (tối thiểu 10 ký tự).
    - Gửi thông báo kèm lý do để người bán điều chỉnh và gửi duyệt lại.
    - Ghi nhận Audit Trail vào `SystemLog` (`Reject_Post`).
    """
    return reject_product(
        product_id=product_id,
        payload=payload,
        current_admin=current_user,
        db=db
    )


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_200_OK,
    summary="Buộc gỡ bỏ vĩnh viễn tin đăng vi phạm nghiêm trọng (Chỉ Super Admin)"
)
def delete_product_by_admin(
    product_id: int = Path(..., ge=1, description="ID tin đăng cần gỡ bỏ"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Buộc gỡ bỏ bài đăng vi phạm nghiêm trọng (BR-ADM-1):
    - Chỉ Super Admin (`role_id = 1`) mới có quyền thực hiện.
    - Soft-delete bài viết (`deleted_at = now()`, `status_id = 4`).
    - Gửi thông báo cảnh cáo người bán và ghi `SystemLog` (`Delete_Post`).
    """
    return admin_delete_product(
        product_id=product_id,
        current_admin=current_admin,
        db=db
    )


# ==============================================================================
# 2. XỬ LÝ TỐ CÁO VI PHẠM (REPORTS HANDLING - SEQUENCE 5 SRS)
# ==============================================================================

@router.get(
    "/reports",
    response_model=PaginatedAdminReportsResponse,
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách phiếu tố cáo vi phạm (Staff / Admin)"
)
def list_admin_reports(
    page: int = Query(1, ge=1, description="Số trang hiện tại"),
    page_size: int = Query(20, ge=1, le=100, description="Số phiếu mỗi trang"),
    status_filter: Optional[str] = Query("Pending", description="Trạng thái lọc: 'Pending', 'Resolved', 'Dismissed' hoặc để trống"),
    target_type: Optional[str] = Query(None, description="Loại mục bị tố cáo: 'Product', 'User', 'Comment'"),
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách hàng đợi xử lý tố cáo vi phạm (Seq 5 SRS).
    Hỗ trợ lọc theo trạng thái và đối tượng bị tố cáo.
    """
    return get_admin_reports_list(
        db=db,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        target_type=target_type
    )


@router.get(
    "/reports/{report_id}",
    response_model=AdminReportDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Xem chi tiết phiếu tố cáo và nội dung bị tố cáo (Staff / Admin)"
)
def get_report_detail_for_admin(
    report_id: int = Path(..., ge=1, description="ID phiếu tố cáo cần thẩm tra"),
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """
    Xem chi tiết phiếu tố cáo kèm nội dung thực tế của đối tượng bị tố cáo:
    - Nếu là Product: trả về thông tin bài đăng và người bán.
    - Nếu là User: trả về hồ sơ và trạng thái tài khoản người bị tố cáo.
    - Nếu là Comment: trả về nội dung bình luận vi phạm.
    """
    return get_admin_report_detail(report_id=report_id, db=db)


@router.post(
    "/reports/{report_id}/resolve",
    response_model=ReportResolveResponse,
    status_code=status.HTTP_200_OK,
    summary="Giải quyết tố cáo & áp dụng chế tài xử phạt (Staff / Admin)"
)
def resolve_report(
    report_id: int = Path(..., ge=1, description="ID phiếu tố cáo cần xử lý"),
    payload: ReportResolveRequest = ...,
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """
    Giải quyết tố cáo vi phạm theo cơ chế linh hoạt tại Gate A (Seq 5 SRS):
    - Chuyển `report.status = 'Resolved'`.
    - Tùy chọn cờ chế tài:
      + `ban_user = true`: Khóa tài khoản violator (`isActive = False`), ẩn các tin đang bán.
      + `add_blacklist = true`: Thêm Email & SĐT của violator vào bảng `blacklists`.
      + `delete_target = true`: Gỡ bỏ tin đăng hoặc xóa bình luận vi phạm.
    - Gửi thông báo cảm ơn người gửi tố cáo.
    - Bắt buộc ghi `SystemLog` kiểm toán trong cùng Database Transaction.
    """
    return resolve_user_report(
        report_id=report_id,
        payload=payload,
        current_admin=current_user,
        db=db
    )


@router.post(
    "/reports/{report_id}/dismiss",
    response_model=ReportDismissResponse,
    status_code=status.HTTP_200_OK,
    summary="Bác bỏ phiếu tố cáo sai sự thật / không đủ bằng chứng (Staff / Admin)"
)
def dismiss_report(
    report_id: int = Path(..., ge=1, description="ID phiếu tố cáo cần bác bỏ"),
    payload: ReportDismissRequest = ...,
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """
    Bác bỏ tố cáo sai sự thật hoặc không đủ căn cứ (Sequence 5 SRS):
    - Chuyển `report.status = 'Dismissed'`.
    - Lưu lý do bác bỏ và ghi nhận Audit Trail vào `SystemLog` (`Dismiss_Report`).
    """
    return dismiss_user_report(
        report_id=report_id,
        payload=payload,
        current_admin=current_user,
        db=db
    )
