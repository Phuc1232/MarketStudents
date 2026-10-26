from fastapi import APIRouter, Depends, status, Query, Path
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from src.api.deps import get_db
from src.modules import (
    User,
    ProductApproveResponse, ProductRejectRequest, ProductRejectResponse,
    AdminProductDetailResponse, PaginatedAdminProductsResponse,
    ReportResolveRequest, ReportResolveResponse, ReportDismissRequest, ReportDismissResponse,
    AdminReportDetailResponse, PaginatedAdminReportsResponse,
    AppealDetailResponse, PaginatedAppealsResponse, AppealRejectRequest,
    AppealApproveResponse, AppealRejectResponse,
    AdminUserListItemResponse, PaginatedAdminUsersResponse, AdminUserDetailResponse,
    UserStatusUpdateRequest, UserRoleUpdateRequest,
    BlacklistCreateRequest, BlacklistItemResponse, PaginatedBlacklistResponse,
    SystemLogItemResponse, PaginatedSystemLogsResponse, AdminDashboardStatsResponse
)
from .services import (
    get_current_staff_or_admin,
    get_current_admin,
    # Products
    get_pending_products,
    get_admin_product_detail,
    approve_product,
    reject_product,
    admin_delete_product,
    # Reports
    get_admin_reports_list,
    get_admin_report_detail,
    resolve_user_report,
    dismiss_user_report,
    # Appeals
    get_pending_appeals_list,
    get_appeal_detail,
    approve_appeal,
    reject_appeal,
    # Users
    get_admin_users_list,
    get_admin_user_detail,
    update_user_active_status,
    update_user_role,
    # Blacklists
    get_blacklist_records,
    create_blacklist_entry,
    remove_from_blacklist,
    # Logs & Dashboard
    get_system_logs_list,
    get_admin_dashboard_metrics
)

router = APIRouter(
    prefix="/admin",
    tags=["Admin - Moderation & Management"]
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
    """Lọc toàn bộ sản phẩm có `status_id = 1` (Pending_Approval) và chưa bị xóa mềm (Seq 12)."""
    return get_pending_products(db=db, page=page, page_size=page_size, category_id=category_id)


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
    """Xem toàn diện chi tiết tin đăng phục vụ thẩm định nội dung và thông số kỹ thuật EAV."""
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
    """Phê duyệt tin đăng: chuyển `status_id = 2` (Active), thông báo seller, ghi SystemLog."""
    return approve_product(product_id=product_id, current_admin=current_user, db=db)


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
    """Từ chối tin đăng: chuyển `status_id = 5` (Rejected), yêu cầu lý do tối thiểu 10 ký tự."""
    return reject_product(product_id=product_id, payload=payload, current_admin=current_user, db=db)


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
    """Buộc gỡ bỏ bài đăng vi phạm nghiêm trọng (Chỉ Super Admin - BR-ADM-1)."""
    return admin_delete_product(product_id=product_id, current_admin=current_admin, db=db)


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
    """Lấy danh sách hàng đợi xử lý tố cáo vi phạm (Seq 5 SRS)."""
    return get_admin_reports_list(
        db=db, page=page, page_size=page_size, status_filter=status_filter, target_type=target_type
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
    """Xem chi tiết phiếu tố cáo kèm nội dung thực tế của đối tượng bị tố cáo."""
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
    """Giải quyết tố cáo vi phạm theo cơ chế linh hoạt tại Gate A (Seq 5 SRS)."""
    return resolve_user_report(report_id=report_id, payload=payload, current_admin=current_user, db=db)


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
    """Bác bỏ tố cáo sai sự thật hoặc không đủ căn cứ (Sequence 5 SRS)."""
    return dismiss_user_report(report_id=report_id, payload=payload, current_admin=current_user, db=db)


# ==============================================================================
# 3. THẨM ĐỊNH KHÁNG CÁO DANH TÍNH (APPEALS MODERATION - SEQUENCE 6 SRS)
# ==============================================================================

@router.get(
    "/identity-verifications",
    response_model=PaginatedAppealsResponse,
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách hồ sơ kháng cáo danh tính chờ duyệt (Staff / Admin)"
)
def list_pending_appeals(
    page: int = Query(1, ge=1, description="Số trang"),
    page_size: int = Query(20, ge=1, le=100, description="Số đơn mỗi trang"),
    status_filter: Optional[str] = Query("PENDING", description="Trạng thái lọc: 'PENDING', 'APPROVED', 'REJECTED'"),
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """Xem danh sách hàng đợi hồ sơ kháng cáo CCCD & SIM chính chủ từ các tài khoản bị khóa."""
    return get_pending_appeals_list(db=db, page=page, page_size=page_size, status_filter=status_filter)


@router.get(
    "/identity-verifications/{request_id}",
    response_model=AppealDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Xem chi tiết hồ sơ kháng cáo kèm ảnh CCCD & SIM (Staff / Admin)"
)
def get_appeal_detail_for_admin(
    request_id: int = Path(..., ge=1, description="ID hồ sơ kháng cáo"),
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """Xem toàn bộ hình ảnh giấy tờ CCCD 2 mặt, ảnh SIM chính chủ và lời giải trình của người dùng."""
    return get_appeal_detail(request_id=request_id, db=db)


@router.patch(
    "/identity-verifications/{request_id}/approve",
    response_model=AppealApproveResponse,
    status_code=status.HTTP_200_OK,
    summary="Phê duyệt kháng cáo & Tự động mở khóa tài khoản (Admin)"
)
def approve_user_appeal(
    request_id: int = Path(..., ge=1, description="ID hồ sơ kháng cáo"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Phê duyệt kháng cáo:
    - Chuyển `status = 'APPROVED'`.
    - Tự động mở khóa tài khoản (`isActive = True`).
    - Gỡ Email và Số điện thoại khỏi `blacklists`.
    - Gửi thông báo chúc mừng và ghi nhận Audit Trail.
    """
    return approve_appeal(request_id=request_id, current_admin=current_admin, db=db)


@router.patch(
    "/identity-verifications/{request_id}/reject",
    response_model=AppealRejectResponse,
    status_code=status.HTTP_200_OK,
    summary="Từ chối hồ sơ kháng cáo kèm lý do (Admin)"
)
def reject_user_appeal(
    request_id: int = Path(..., ge=1, description="ID hồ sơ kháng cáo"),
    payload: AppealRejectRequest = ...,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Từ chối kháng cáo: chuyển `status = 'REJECTED'`, giữ nguyên khóa tài khoản và lưu lý do."""
    return reject_appeal(request_id=request_id, payload=payload, current_admin=current_admin, db=db)


# ==============================================================================
# 4. QUẢN LÝ NGƯỜI DÙNG TOÀN SÀN (USER MANAGEMENT - SRS 1.1, USE CASE 2.3)
# ==============================================================================

@router.get(
    "/users",
    response_model=PaginatedAdminUsersResponse,
    status_code=status.HTTP_200_OK,
    summary="Tra cứu danh sách người dùng toàn sàn (Staff / Admin)"
)
def list_users_for_admin(
    page: int = Query(1, ge=1, description="Số trang"),
    page_size: int = Query(20, ge=1, le=100, description="Số tài khoản mỗi trang"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo Email, Họ tên hoặc Số điện thoại"),
    role_id: Optional[int] = Query(None, description="Lọc vai trò: 1 (Admin), 2 (Normal), 3 (Student), 4 (Staff)"),
    is_active: Optional[bool] = Query(None, description="Lọc trạng thái: True (Active), False (Banned)"),
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """Tra cứu danh sách người dùng toàn sàn hỗ trợ tìm kiếm đa tiêu chí và phân trang."""
    return get_admin_users_list(
        db=db, page=page, page_size=page_size, search=search, role_id=role_id, is_active=is_active
    )


@router.get(
    "/users/{user_id}",
    response_model=AdminUserDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Xem hồ sơ toàn diện người dùng kèm ví tiền & thống kê tin đăng (Staff / Admin)"
)
def get_user_detail_for_admin(
    user_id: int = Path(..., ge=1, description="ID người dùng cần kiểm tra"),
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """Xem chi tiết hồ sơ cá nhân, số dư ví hiện tại, tổng tin đăng, số tin đã bán và số lần bị tố cáo."""
    return get_admin_user_detail(user_id=user_id, db=db)


@router.patch(
    "/users/{user_id}/status",
    status_code=status.HTTP_200_OK,
    summary="Khóa hoặc Mở khóa tài khoản người dùng thủ công (Admin)"
)
def update_user_status(
    user_id: int = Path(..., ge=1, description="ID người dùng"),
    payload: UserStatusUpdateRequest = ...,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Khóa/mở khóa tài khoản thủ công:
    - Nếu khóa: Ẩn các tin đăng đang bán, tùy chọn thêm vào Blacklist.
    - Nếu mở khóa: Gỡ khỏi Blacklist.
    - Chặn Admin tự khóa tài khoản của chính mình.
    """
    return update_user_active_status(user_id=user_id, payload=payload, current_admin=current_admin, db=db)


@router.patch(
    "/users/{user_id}/role",
    status_code=status.HTTP_200_OK,
    summary="Phân quyền / hạ quyền nhân viên sàn (Chỉ Super Admin)"
)
def change_user_role(
    user_id: int = Path(..., ge=1, description="ID người dùng cần thay đổi quyền"),
    payload: UserRoleUpdateRequest = ...,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Chỉ Super Admin tối cao (`role_id = 1`) mới có quyền thăng cấp hoặc hạ quyền nhân viên."""
    return update_user_role(user_id=user_id, payload=payload, current_admin=current_admin, db=db)


# ==============================================================================
# 5. QUẢN LÝ DANH SÁCH ĐEN (BLACKLIST MANAGEMENT - SRS 1.1)
# ==============================================================================

@router.get(
    "/blacklists",
    response_model=PaginatedBlacklistResponse,
    status_code=status.HTTP_200_OK,
    summary="Tra cứu danh sách đen các Email & Số điện thoại bị cấm (Staff / Admin)"
)
def list_blacklists(
    page: int = Query(1, ge=1, description="Số trang"),
    page_size: int = Query(20, ge=1, le=100, description="Số mục mỗi trang"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo định danh hoặc lý do cấm"),
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """Tra cứu danh sách định danh bị cấm khởi tạo tài khoản trên sàn."""
    return get_blacklist_records(db=db, page=page, page_size=page_size, search=search)


@router.post(
    "/blacklists",
    response_model=BlacklistItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Thêm định danh vào danh sách đen thủ công (Admin)"
)
def add_blacklist_entry(
    payload: BlacklistCreateRequest = ...,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Chặn trước Email hoặc SĐT có dấu hiệu lừa đảo khỏi hệ thống."""
    return create_blacklist_entry(payload=payload, current_admin=current_admin, db=db)


@router.delete(
    "/blacklists/{blacklist_id}",
    status_code=status.HTTP_200_OK,
    summary="Gỡ bỏ định danh khỏi danh sách đen (Admin)"
)
def delete_blacklist_entry(
    blacklist_id: int = Path(..., ge=1, description="ID bản ghi blacklist"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Gỡ bỏ lệnh cấm đối với Email hoặc Số điện thoại."""
    return remove_from_blacklist(blacklist_id=blacklist_id, current_admin=current_admin, db=db)


# ==============================================================================
# 6. NHẬT KÝ HỆ THỐNG & THỐNG KÊ SÀN (AUDIT LOGS & DASHBOARD - BR-ADM-6)
# ==============================================================================

@router.get(
    "/system-logs",
    response_model=PaginatedSystemLogsResponse,
    status_code=status.HTTP_200_OK,
    summary="Tra cứu nhật ký thao tác kiểm toán hệ thống (Staff / Admin)"
)
def list_system_logs(
    page: int = Query(1, ge=1, description="Số trang"),
    page_size: int = Query(20, ge=1, le=100, description="Số dòng log mỗi trang"),
    action_filter: Optional[str] = Query(None, description="Lọc theo từ khóa hành động"),
    admin_id: Optional[int] = Query(None, description="Lọc theo ID người thực hiện"),
    target_table: Optional[str] = Query(None, description="Lọc theo bảng dữ liệu mục tiêu"),
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """Xem toàn bộ lịch sử Audit Trail của đội ngũ Admin và Staff phục vụ kiểm toán."""
    return get_system_logs_list(
        db=db,
        page=page,
        page_size=page_size,
        action_filter=action_filter,
        admin_id=admin_id,
        target_table=target_table
    )


@router.get(
    "/dashboard/stats",
    response_model=AdminDashboardStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Tổng hợp chỉ số vận hành & kiểm duyệt sàn theo thời gian thực (Staff / Admin)"
)
def get_dashboard_statistics(
    current_user: User = Depends(get_current_staff_or_admin),
    db: Session = Depends(get_db)
):
    """Xem các chỉ số KPI: người dùng, tin đăng các trạng thái, hàng đợi tố cáo và kháng cáo."""
    return get_admin_dashboard_metrics(db=db)
