from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


# ==============================================================================
# 1. SCHEMAS KIỂM DUYỆT TIN ĐĂNG (PRODUCT MODERATION)
# ==============================================================================

class ProductApproveResponse(BaseModel):
    """Phản hồi sau khi Admin phê duyệt tin đăng sang Active (Seq 12)"""
    product_id: int
    status_id: int = 2
    status_name: str = "Active"
    message: str = "Tin đăng đã được phê duyệt thành công và hiển thị trên UniMarket"
    approved_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductRejectRequest(BaseModel):
    """Payload Admin gửi lý do từ chối tin đăng vi phạm quy chế"""
    reject_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Lý do từ chối tin đăng (tối thiểu 10 ký tự, tối đa 500 ký tự)"
    )


class ProductRejectResponse(BaseModel):
    """Phản hồi sau khi Admin từ chối tin đăng"""
    product_id: int
    status_id: int = 5
    status_name: str = "Rejected"
    reject_reason: str
    message: str = "Đã từ chối tin đăng và gửi thông báo kèm lý do cho người bán"
    rejected_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminProductImageDto(BaseModel):
    """DTO hiển thị ảnh sản phẩm kèm thứ tự"""
    image_id: int
    image_url: str
    display_order: int
    is_thumbnail: bool

    model_config = ConfigDict(from_attributes=True)


class AdminProductAttributeDto(BaseModel):
    """DTO thuộc tính động EAV của sản phẩm"""
    attribute_id: int
    attribute_name: str
    value_text: Optional[str] = None
    value_num: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AdminSellerSummaryDto(BaseModel):
    """Tóm tắt thông tin người bán cho Admin đối soát"""
    user_id: int
    email: str
    full_name: str
    phone_number: Optional[str] = None
    avatar_url: Optional[str] = None
    role_id: int
    is_active: bool
    rating_avg: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class AdminProductListItemResponse(BaseModel):
    """Mục tin đăng trong danh sách hàng đợi kiểm duyệt"""
    product_id: int
    title: str
    price: float
    thumbnail_url: Optional[str] = None
    category_name: str
    subcategory_name: str
    condition_name: Optional[str] = None
    seller: AdminSellerSummaryDto
    status_id: int
    status_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedAdminProductsResponse(BaseModel):
    """Kết quả phân trang danh sách tin chờ duyệt / tin admin"""
    total: int
    page: int
    page_size: int
    items: List[AdminProductListItemResponse]

    model_config = ConfigDict(from_attributes=True)


class AdminProductDetailResponse(BaseModel):
    """Xem toàn bộ chi tiết tin đăng phục vụ Admin thẩm định kỹ lưỡng"""
    product_id: int
    title: str
    price: float
    description: Optional[str] = None
    thumbnails: Optional[str] = None
    category_id: int
    category_name: str
    subcategory_id: int
    subcategory_name: str
    condition_id: int
    condition_name: Optional[str] = None
    status_id: int
    status_name: str
    seller: AdminSellerSummaryDto
    buyer_id: Optional[int] = None
    images: List[AdminProductImageDto] = []
    attributes: List[AdminProductAttributeDto] = []
    views_count: int = 0
    favorites_count: int = 0
    reports_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 2. SCHEMAS XỬ LÝ TỐ CÁO VI PHẠM (REPORTS HANDLING)
# ==============================================================================

class ReportResolveRequest(BaseModel):
    """Payload xử lý báo cáo vi phạm theo cơ chế linh hoạt tại Gate A"""
    action_taken: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Mô tả tóm tắt biện pháp chế tài đã thực hiện (vd: Khóa tài khoản gian lận, Gỡ tin rác)"
    )
    ban_user: bool = Field(
        default=False,
        description="Khóa vĩnh viễn tài khoản đối tượng vi phạm (isActive = False)"
    )
    add_blacklist: bool = Field(
        default=False,
        description="Đưa Email và Số điện thoại đối tượng vi phạm vào danh sách đen blacklists"
    )
    delete_target: bool = Field(
        default=False,
        description="Xóa mềm tin đăng vi phạm hoặc xóa bình luận độc hại"
    )
    admin_notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Ghi chú nội bộ dành cho đội ngũ Quản trị viên"
    )


class ReportResolveResponse(BaseModel):
    """Phản hồi sau khi giải quyết phiếu tố cáo"""
    report_id: int
    status: str = "Resolved"
    action_taken: str
    is_user_banned: bool
    is_target_deleted: bool
    resolved_at: datetime
    message: str = "Đã giải quyết tố cáo, áp dụng chế tài, thông báo cho người báo cáo và ghi nhận audit log"

    model_config = ConfigDict(from_attributes=True)


class ReportDismissRequest(BaseModel):
    """Payload bác bỏ báo cáo sai sự thật hoặc không đủ bằng chứng vi phạm"""
    dismiss_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Lý do bác bỏ phiếu tố cáo (tối thiểu 10 ký tự)"
    )


class ReportDismissResponse(BaseModel):
    """Phản hồi sau khi bác bỏ tố cáo"""
    report_id: int
    status: str = "Dismissed"
    dismiss_reason: str
    dismissed_at: datetime
    message: str = "Đã bác bỏ tố cáo và lưu vết nhật ký hệ thống"

    model_config = ConfigDict(from_attributes=True)


class AdminReportListItemResponse(BaseModel):
    """Mục báo cáo trong danh sách hàng đợi xử lý"""
    report_id: int
    reporter_id: int
    reporter_name: str
    reporter_avatar: Optional[str] = None
    reason_id: int
    reason_content: str
    target_type: str  # Product, User, Comment
    target_id: int
    status: str       # Pending, Resolved, Dismissed
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedAdminReportsResponse(BaseModel):
    """Kết quả phân trang danh sách tố cáo"""
    total: int
    page: int
    page_size: int
    items: List[AdminReportListItemResponse]

    model_config = ConfigDict(from_attributes=True)


class AdminReportDetailResponse(BaseModel):
    """Chi tiết phiếu tố cáo và nội dung thực tế của đối tượng bị tố cáo"""
    report_id: int
    reporter_id: int
    reporter_name: str
    reporter_email: str
    reason_id: int
    reason_content: str
    target_type: str
    target_id: int
    status: str
    target_data: Optional[Dict[str, Any]] = None  # Chi tiết Product / User / Comment bị report
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 3. SCHEMAS KHÁNG CÁO & XÁC MINH DANH TÍNH (IDENTITY VERIFICATION / APPEAL)
# ==============================================================================

class AppealCreateRequest(BaseModel):
    """Payload người dùng bị khóa nộp hồ sơ kháng cáo CCCD & SIM (Seq 6)"""
    contact_phone: str = Field(
        ...,
        pattern=r"^(0|\+84)[0-9]{9,10}$",
        description="Số điện thoại liên hệ chính chủ (10-11 số)"
    )
    other_phone: Optional[str] = Field(
        None,
        description="Số điện thoại phụ hoặc số người thân liên hệ dự phòng"
    )
    cccd_front_url: str = Field(
        ...,
        description="Đường dẫn URL ảnh mặt trước Căn cước công dân (rõ nét, không lóa)"
    )
    cccd_back_url: str = Field(
        ...,
        description="Đường dẫn URL ảnh mặt sau Căn cước công dân"
    )
    sim_ownership_url: str = Field(
        ...,
        description="Đường dẫn URL ảnh chụp tin nhắn tra cứu TTTB (1414) hoặc ảnh app nhà mạng xác minh chính chủ"
    )
    note: Optional[str] = Field(
        None,
        max_length=500,
        description="Lời giải trình hoặc cam kết tuân thủ quy chế từ người dùng"
    )


class AppealDetailResponse(BaseModel):
    """Chi tiết hồ sơ kháng cáo danh tính để Admin đối soát"""
    request_id: int
    user_id: int
    user_email: str
    user_name: str
    contact_phone: str
    other_phone: Optional[str] = None
    cccd_front_url: str
    cccd_back_url: str
    sim_ownership_url: str
    status: str  # PENDING, APPROVED, REJECTED
    note: Optional[str] = None
    handle_by_id: Optional[int] = None
    handler_name: Optional[str] = None
    submit_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MyAppelStatusResponse(BaseModel):
    """Tình trạng hồ sơ kháng cáo gần nhất trả về cho Banned User"""
    request_id: int
    status: str
    submit_at: datetime
    note: Optional[str] = None
    message: str

    model_config = ConfigDict(from_attributes=True)


class PaginatedAppealsResponse(BaseModel):
    """Danh sách phân trang các đơn kháng cáo"""
    total: int
    page: int
    page_size: int
    items: List[AppealDetailResponse]

    model_config = ConfigDict(from_attributes=True)


class AppealRejectRequest(BaseModel):
    """Lý do từ chối đơn kháng cáo"""
    reject_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Lý do từ chối hồ sơ (vd: Ảnh CCCD bị nhòe/mất góc, SIM không khớp thông tin)"
    )


class AppealApproveResponse(BaseModel):
    """Phản hồi sau khi duyệt kháng cáo và mở khóa tài khoản"""
    request_id: int
    status: str = "APPROVED"
    user_id: int
    is_user_active: bool = True
    approved_at: datetime
    message: str = "Đã phê duyệt kháng cáo, mở khóa tài khoản người dùng và gỡ khỏi danh sách đen"

    model_config = ConfigDict(from_attributes=True)


class AppealRejectResponse(BaseModel):
    """Phản hồi sau khi bác bỏ kháng cáo"""
    request_id: int
    status: str = "REJECTED"
    user_id: int
    reject_reason: str
    rejected_at: datetime
    message: str = "Đã từ chối đơn kháng cáo và giữ nguyên tình trạng khóa tài khoản"

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 4. SCHEMAS QUẢN LÝ NGƯỜI DÙNG & DANH SÁCH ĐEN (USER & BLACKLIST MANAGEMENT)
# ==============================================================================

class AdminUserListItemResponse(BaseModel):
    """Thông tin tóm tắt người dùng trong danh sách quản lý tài khoản"""
    user_id: int
    email: str
    full_name: str
    avatar_url: Optional[str] = None
    phone_number: Optional[str] = None
    role_id: int
    role_name: str
    account_type: Optional[str] = None
    is_active: bool
    is_verified_student: bool = False
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedAdminUsersResponse(BaseModel):
    """Kết quả phân trang danh sách người dùng"""
    total: int
    page: int
    page_size: int
    items: List[AdminUserListItemResponse]

    model_config = ConfigDict(from_attributes=True)


class AdminUserDetailResponse(BaseModel):
    """Hồ sơ toàn diện của một người dùng bao gồm ví tiền, tin đăng và tố cáo vi phạm"""
    user_id: int
    email: str
    full_name: str
    avatar_url: Optional[str] = None
    phone_number: Optional[str] = None
    bio: Optional[str] = None
    role_id: int
    role_name: str
    account_type: Optional[str] = None
    is_active: bool
    is_verified_student: bool = False
    edu_email: Optional[str] = None
    total_products_posted: int = 0
    total_products_sold: int = 0
    total_reports_received: int = 0
    rating_avg: float = 0.0
    wallet_balance: float = 0.0
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserStatusUpdateRequest(BaseModel):
    """Payload khóa hoặc mở khóa tài khoản thủ công"""
    is_active: bool = Field(
        ...,
        description="Trạng thái tài khoản mong muốn: True (Mở khóa), False (Khóa tài khoản)"
    )
    reason: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Lý do thay đổi trạng thái tài khoản"
    )
    add_to_blacklist: bool = Field(
        default=False,
        description="Nếu khóa tài khoản, có đưa Email & SĐT vào danh sách đen Blacklist hay không"
    )


class UserRoleUpdateRequest(BaseModel):
    """Payload nâng cấp hoặc thay đổi vai trò người dùng (Chỉ Super Admin)"""
    role_id: int = Field(
        ...,
        description="Mã vai trò mới: 1 (Super Admin), 2 (Normal User), 3 (Student), 4 (Staff)"
    )


class BlacklistCreateRequest(BaseModel):
    """Thêm định danh vào danh sách đen thủ công"""
    blocked_value: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Email hoặc Số điện thoại cần chặn khỏi hệ thống"
    )
    reason: str = Field(
        ...,
        min_length=5,
        description="Lý do đưa vào danh sách cấm"
    )


class BlacklistItemResponse(BaseModel):
    """Mục định danh trong danh sách đen"""
    blacklist_id: int
    admin_id: int
    admin_email: Optional[str] = None
    blocked_value: str
    reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedBlacklistResponse(BaseModel):
    """Kết quả phân trang danh sách đen"""
    total: int
    page: int
    page_size: int
    items: List[BlacklistItemResponse]

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 5. SCHEMAS NHẬT KÝ HỆ THỐNG & THỐNG KÊ SÀN (SYSTEM LOGS & DASHBOARD METRICS)
# ==============================================================================

class SystemLogItemResponse(BaseModel):
    """Mục nhật ký hành động kiểm toán của Admin/Staff (Audit Trail)"""
    log_id: int
    admin_id: int
    admin_name: str
    admin_email: str
    action: str
    target_table: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedSystemLogsResponse(BaseModel):
    """Kết quả phân trang nhật ký kiểm toán hệ thống"""
    total: int
    page: int
    page_size: int
    items: List[SystemLogItemResponse]

    model_config = ConfigDict(from_attributes=True)


class AdminDashboardStatsResponse(BaseModel):
    """Chỉ số vận hành tổng quan toàn sàn UniMarket theo thời gian thực"""
    # Người dùng
    total_users: int
    active_users: int
    banned_users: int
    verified_students: int

    # Tin đăng
    total_products: int
    pending_products: int
    active_products: int
    sold_products: int
    rejected_products: int

    # Hàng đợi vận hành
    pending_reports: int
    resolved_reports: int
    pending_appeals: int

    model_config = ConfigDict(from_attributes=True)
