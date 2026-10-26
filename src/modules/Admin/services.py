from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, and_, or_, desc
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from src.api.deps import get_db
from src.modules.User.service import get_current_user
from src.modules import (
    User, userProfile, userStats, StudentVerification, Role,
    Product, ProductImage, ProductAttribute, ProductStatus, ProductCondition, SubCategory, Category,
    Report, ReportReason, Notification, SystemLog, Blacklist, IdentityVerification, Comment, Wallet
)
from src.modules.Interaction.services import get_user_display_name, get_user_avatar
from .schemas import (
    ProductApproveResponse, ProductRejectRequest, ProductRejectResponse,
    AdminProductDetailResponse, AdminProductListItemResponse, PaginatedAdminProductsResponse,
    AdminProductImageDto, AdminProductAttributeDto, AdminSellerSummaryDto,
    ReportResolveRequest, ReportResolveResponse, ReportDismissRequest, ReportDismissResponse,
    AdminReportListItemResponse, PaginatedAdminReportsResponse, AdminReportDetailResponse,
    AppealCreateRequest, AppealDetailResponse, MyAppelStatusResponse, PaginatedAppealsResponse,
    AppealRejectRequest, AppealApproveResponse, AppealRejectResponse,
    AdminUserListItemResponse, PaginatedAdminUsersResponse, AdminUserDetailResponse,
    UserStatusUpdateRequest, UserRoleUpdateRequest,
    BlacklistCreateRequest, BlacklistItemResponse, PaginatedBlacklistResponse,
    SystemLogItemResponse, PaginatedSystemLogsResponse, AdminDashboardStatsResponse
)


# ==============================================================================
# 1. RBAC AUTHENTICATION & AUTHORIZATION DEPENDENCIES (DEPENDENCY CHAINING)
# ==============================================================================

def get_current_staff_or_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency kiểm tra quyền truy cập Quản trị viên hoặc Nhân viên kiểm duyệt:
    - Kế thừa trực tiếp từ get_current_user (Dependency Chaining, tái sử dụng logic decode JWT).
    - Tài khoản đang hoạt động (isActive == True).
    - Vai trò role_id thuộc nhóm (1: Admin, 4: Staff).
    Nếu không thỏa mãn -> Ném HTTP 403 Forbidden.
    """
    if not current_user.isActive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản quản trị của bạn đã bị khóa hoặc vô hiệu hóa!"
        )

    # role_id = 1: Super Admin, role_id = 4: Staff (Nhân viên kiểm duyệt)
    if current_user.role_id not in (1, 4):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Truy cập bị từ chối: Khu vực này chỉ dành cho Ban Quản Trị và Nhân viên kiểm duyệt sàn!"
        )

    return current_user


def get_current_admin(
    current_admin: User = Depends(get_current_staff_or_admin)
) -> User:
    """
    Dependency kiểm tra quyền Super Admin tối cao (role_id == 1):
    - Kế thừa trực tiếp qua chuỗi Dependency Chaining từ get_current_staff_or_admin.
    - Dùng cho các thao tác nhạy cảm: Phân quyền nhân viên, Xóa bài viết vi phạm, Quản lý blacklist.
    """
    if current_admin.role_id != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Thao tác bị từ chối: Chỉ Quản trị viên cấp cao (Super Admin) mới có quyền thực hiện nghiệp vụ này!"
        )
    return current_admin


def get_current_banned_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency chuyên biệt dành cho tài khoản bị khóa (isActive == False):
    - Tái sử dụng get_current_user để trích xuất User từ Token hợp lệ.
    - Cho phép user truy cập cổng gửi hồ sơ kháng cáo CCCD (/identity-verification/appeal).
    - Nếu tài khoản vẫn đang hoạt động bình thường -> Ném HTTP 400 Bad Request.
    """
    if current_user.isActive is True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản của bạn đang hoạt động bình thường, không cần nộp đơn kháng cáo mở khóa!"
        )

    return current_user


# ==============================================================================
# 2. HÀM TRỢ NĂNG GHI LOG VÀ THÔNG BÁO TỰ ĐỘNG
# ==============================================================================

def record_system_log(
    admin_id: int,
    action: str,
    target_table: str,
    db: Session
) -> SystemLog:
    """Tạo bản ghi Audit Trail bắt buộc trong cùng Transaction (BR-ADM-6)"""
    log_entry = SystemLog(
        admin_id=admin_id,
        action=action[:100],
        target_table=target_table[:100],
        timestamp=datetime.now(timezone.utc)
    )
    db.add(log_entry)
    return log_entry


def send_system_notification(
    user_id: int,
    title: str,
    message: str,
    action_link: Optional[str],
    db: Session
) -> Notification:
    """Gửi thông báo hệ thống trực tiếp vào hộp thư người dùng"""
    notif = Notification(
        user_id=user_id,
        title=title[:255],
        message=message,
        action_link=action_link,
        is_read=False
    )
    db.add(notif)
    return notif


def _build_admin_seller_dto(seller: Optional[User]) -> AdminSellerSummaryDto:
    """Đóng gói DTO người bán phục vụ Admin kiểm tra"""
    if not seller:
        return AdminSellerSummaryDto(
            user_id=0,
            email="unknown@unimarket.vn",
            full_name="Người dùng không xác định",
            phone_number=None,
            avatar_url=None,
            role_id=2,
            is_active=False,
            rating_avg=0.0
        )
    phone = seller.profile.phone_number if seller.profile else None
    rating = seller.stats.rating_avg if seller.stats else 0.0
    return AdminSellerSummaryDto(
        user_id=seller.id,
        email=seller.Email,
        full_name=get_user_display_name(seller),
        phone_number=phone,
        avatar_url=get_user_avatar(seller),
        role_id=seller.role_id,
        is_active=bool(seller.isActive),
        rating_avg=rating or 0.0
    )


# ==============================================================================
# 3. SERVICES KIỂM DUYỆT TIN ĐĂNG (PRODUCT MODERATION - SEQUENCE 12)
# ==============================================================================

def get_pending_products(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    category_id: Optional[int] = None
) -> PaginatedAdminProductsResponse:
    """
    Lấy danh sách tin đăng đang chờ duyệt (status_id = 1, deleted_at is None):
    - Hỗ trợ phân trang page, page_size.
    - Lọc tùy chọn theo danh mục cha category_id.
    """
    stmt = (
        select(Product)
        .where(
            Product.status_id == 1,
            Product.deleted_at.is_(None)
        )
        .options(
            selectinload(Product.seller).selectinload(User.profile),
            selectinload(Product.seller).selectinload(User.stats),
            selectinload(Product.subcategory).selectinload(SubCategory.category),
            selectinload(Product.condition),
            selectinload(Product.status),
            selectinload(Product.images)
        )
        .order_by(Product.product_id.asc())
    )

    if category_id:
        stmt = stmt.join(Product.subcategory).where(SubCategory.category_id == category_id)

    # Đếm tổng số bản ghi
    count_stmt = select(func.count(Product.product_id)).where(
        Product.status_id == 1,
        Product.deleted_at.is_(None)
    )
    if category_id:
        count_stmt = count_stmt.join(Product.subcategory).where(SubCategory.category_id == category_id)
    total = db.scalar(count_stmt) or 0

    # Phân trang
    offset = (page - 1) * page_size
    products = db.scalars(stmt.offset(offset).limit(page_size)).all()

    items: List[AdminProductListItemResponse] = []
    for prod in products:
        thumb = prod.thumbnails
        if not thumb and prod.images:
            thumb = prod.images[0].image_url

        cat_name = prod.subcategory.category.name if (prod.subcategory and prod.subcategory.category) else "Khác"
        sub_name = prod.subcategory.name if prod.subcategory else "Khác"
        cond_name = prod.condition.condition_name if prod.condition else None
        status_name = prod.status.status_name if prod.status else "Pending_Approval"
        created_time = getattr(prod, "CreatedAt", datetime.now(timezone.utc))

        items.append(
            AdminProductListItemResponse(
                product_id=prod.product_id,
                title=prod.title,
                price=prod.price,
                thumbnail_url=thumb,
                category_name=cat_name,
                subcategory_name=sub_name,
                condition_name=cond_name,
                seller=_build_admin_seller_dto(prod.seller),
                status_id=prod.status_id,
                status_name=status_name,
                created_at=created_time
            )
        )

    return PaginatedAdminProductsResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


def get_admin_product_detail(
    product_id: int,
    db: Session
) -> AdminProductDetailResponse:
    """
    Xem chi tiết sản phẩm phục vụ Admin thẩm định kỹ lưỡng:
    - Hiển thị đầy đủ hình ảnh, thuộc tính EAV, người bán, và số liệu thống kê tương tác.
    """
    stmt = (
        select(Product)
        .where(Product.product_id == product_id)
        .options(
            selectinload(Product.seller).selectinload(User.profile),
            selectinload(Product.seller).selectinload(User.stats),
            selectinload(Product.subcategory).selectinload(SubCategory.category),
            selectinload(Product.condition),
            selectinload(Product.status),
            selectinload(Product.images),
            selectinload(Product.value).selectinload(ProductAttribute.attribute)
        )
    )
    product = db.scalars(stmt).first()
    if not product or product.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tin đăng ID {product_id} không tồn tại hoặc đã bị xóa"
        )

    # Đếm thống kê
    views_cnt = db.scalar(select(func.count()).select_from(Product).where(Product.product_id == product_id)) or 0
    fav_cnt = db.scalar(select(func.count()).where(Product.product_id == product_id)) or 0
    rep_cnt = db.scalar(
        select(func.count(Report.report_id)).where(
            Report.target_type == "Product",
            Report.target_id == product_id
        )
    ) or 0

    cat_id = product.subcategory.category_id if product.subcategory else 0
    cat_name = product.subcategory.category.name if (product.subcategory and product.subcategory.category) else "Khác"
    sub_name = product.subcategory.name if product.subcategory else "Khác"
    cond_name = product.condition.condition_name if product.condition else None
    status_name = product.status.status_name if product.status else "Pending_Approval"

    images_dto = [
        AdminProductImageDto(
            image_id=img.image_id,
            image_url=img.image_url,
            display_order=img.display_order or 0,
            is_thumbnail=bool(img.is_thumbnail)
        )
        for img in product.images
    ]

    attributes_dto = [
        AdminProductAttributeDto(
            attribute_id=val.attribute_id,
            attribute_name=val.attribute.name if val.attribute else f"Attr #{val.attribute_id}",
            value_text=val.Value_Text,
            value_num=val.Value_Num
        )
        for val in product.value
    ]

    created_time = getattr(product, "CreatedAt", datetime.now(timezone.utc))
    updated_time = getattr(product, "UpdateAt", datetime.now(timezone.utc))

    return AdminProductDetailResponse(
        product_id=product.product_id,
        title=product.title,
        price=product.price,
        description=product.description,
        thumbnails=product.thumbnails,
        category_id=cat_id,
        category_name=cat_name,
        subcategory_id=product.sub_category_id,
        subcategory_name=sub_name,
        condition_id=product.condition_id,
        condition_name=cond_name,
        status_id=product.status_id,
        status_name=status_name,
        seller=_build_admin_seller_dto(product.seller),
        buyer_id=product.buyer_id,
        images=images_dto,
        attributes=attributes_dto,
        views_count=views_cnt,
        favorites_count=fav_cnt,
        reports_count=rep_cnt,
        created_at=created_time,
        updated_at=updated_time
    )


def approve_product(
    product_id: int,
    current_admin: User,
    db: Session
) -> ProductApproveResponse:
    """
    Phê duyệt tin đăng (Sequence 12 SRS):
    - Kiểm tra tin tồn tại và đang ở trạng thái Pending_Approval (status_id = 1) hoặc Rejected (status_id = 5).
    - Cập nhật status_id = 2 (Active).
    - Gửi Notification cho người bán.
    - Ghi SystemLog kiểm toán (Approve_Post).
    """
    product = db.get(Product, product_id)
    if not product or product.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tin đăng ID {product_id} không tồn tại hoặc đã bị xóa"
        )

    if product.status_id == 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tin đăng này đã ở trạng thái Active (Đang hiển thị)!"
        )

    # Cập nhật trạng thái
    product.status_id = 2  # Active

    # Gửi thông báo cho người bán
    send_system_notification(
        user_id=product.seller_id,
        title="Tin đăng của bạn đã được phê duyệt!",
        message=f"Chúc mừng bạn! Tin đăng '{product.title}' đã được Ban Quản Trị phê duyệt và hiện đang hiển thị công khai trên UniMarket.",
        action_link=f"/products/{product.product_id}",
        db=db
    )

    # Ghi nhận Audit Trail
    record_system_log(
        admin_id=current_admin.id,
        action=f"Approve_Post: ID {product.product_id} - '{product.title[:40]}'",
        target_table="products",
        db=db
    )

    db.commit()
    return ProductApproveResponse(
        product_id=product.product_id,
        status_id=2,
        status_name="Active",
        message="Tin đăng đã được phê duyệt thành công",
        approved_at=datetime.now(timezone.utc)
    )


def reject_product(
    product_id: int,
    payload: ProductRejectRequest,
    current_admin: User,
    db: Session
) -> ProductRejectResponse:
    """
    Từ chối tin đăng vi phạm (Sequence 12 SRS):
    - Cập nhật status_id = 5 (Rejected).
    - Gửi Notification kèm lý do chi tiết để người bán chỉnh sửa.
    - Ghi SystemLog kiểm toán (Reject_Post).
    """
    product = db.get(Product, product_id)
    if not product or product.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tin đăng ID {product_id} không tồn tại hoặc đã bị xóa"
        )

    # Cập nhật trạng thái
    product.status_id = 5  # Rejected

    # Gửi thông báo cho người bán
    send_system_notification(
        user_id=product.seller_id,
        title="Tin đăng chưa được phê duyệt",
        message=f"Tin đăng '{product.title}' bị từ chối duyệt. Lý do: {payload.reject_reason}. Vui lòng cập nhật lại thông tin để được duyệt lại.",
        action_link=f"/seller/products/{product.product_id}/edit",
        db=db
    )

    # Ghi nhận Audit Trail
    record_system_log(
        admin_id=current_admin.id,
        action=f"Reject_Post: ID {product.product_id} - Lý do: {payload.reject_reason[:40]}",
        target_table="products",
        db=db
    )

    db.commit()
    return ProductRejectResponse(
        product_id=product.product_id,
        status_id=5,
        status_name="Rejected",
        reject_reason=payload.reject_reason,
        message="Đã từ chối tin đăng và thông báo cho người bán",
        rejected_at=datetime.now(timezone.utc)
    )


def admin_delete_product(
    product_id: int,
    current_admin: User,
    db: Session
) -> Dict[str, Any]:
    """
    Buộc gỡ bỏ tin vi phạm nghiêm trọng (Chỉ Super Admin - BR-ADM-1):
    - Soft delete: gán deleted_at = now().
    - Gửi thông báo cảnh cáo người bán.
    - Ghi SystemLog (Delete_Post).
    """
    product = db.get(Product, product_id)
    if not product or product.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tin đăng ID {product_id} không tồn tại hoặc đã bị gỡ bỏ trước đó"
        )

    now_utc = datetime.now(timezone.utc)
    product.deleted_at = now_utc
    product.status_id = 4  # Hidden

    send_system_notification(
        user_id=product.seller_id,
        title="Tin đăng bị gỡ bỏ do vi phạm nghiêm trọng",
        message=f"Tin đăng '{product.title}' đã bị Ban Quản Trị buộc gỡ bỏ khỏi hệ thống do vi phạm nghiêm trọng tiêu chuẩn cộng đồng.",
        action_link=None,
        db=db
    )

    record_system_log(
        admin_id=current_admin.id,
        action=f"Delete_Post: ID {product.product_id} - '{product.title[:40]}'",
        target_table="products",
        db=db
    )

    db.commit()
    return {
        "message": f"Đã gỡ bỏ vĩnh viễn tin đăng ID {product_id} khỏi sàn UniMarket",
        "product_id": product_id,
        "deleted_at": now_utc
    }


# ==============================================================================
# 4. SERVICES XỬ LÝ TỐ CÁO VI PHẠM (REPORTS HANDLING - SEQUENCE 5)
# ==============================================================================

def get_admin_reports_list(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = "Pending",
    target_type: Optional[str] = None
) -> PaginatedAdminReportsResponse:
    """
    Lấy danh sách phiếu tố cáo vi phạm:
    - status_filter: 'Pending' (mặc định), 'Resolved', 'Dismissed', hoặc None (tất cả).
    - target_type: 'Product', 'User', 'Comment' hoặc None.
    """
    stmt = (
        select(Report)
        .options(
            selectinload(Report.reason),
            selectinload(Report.user).selectinload(User.profile)
        )
        .order_by(Report.report_id.desc())
    )

    conditions = []
    if status_filter:
        conditions.append(Report.status == status_filter)
    if target_type:
        conditions.append(Report.target_type == target_type)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    # Đếm tổng
    count_stmt = select(func.count(Report.report_id))
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    total = db.scalar(count_stmt) or 0

    offset = (page - 1) * page_size
    reports = db.scalars(stmt.offset(offset).limit(page_size)).all()

    items: List[AdminReportListItemResponse] = []
    for rep in reports:
        reporter_name = get_user_display_name(rep.user)
        reporter_avatar = get_user_avatar(rep.user)
        reason_txt = rep.reason.content if rep.reason else "Lý do khác"
        created_time = getattr(rep, "CreatedAt", datetime.now(timezone.utc))

        items.append(
            AdminReportListItemResponse(
                report_id=rep.report_id,
                reporter_id=rep.reporter_id,
                reporter_name=reporter_name,
                reporter_avatar=reporter_avatar,
                reason_id=rep.reason_id,
                reason_content=reason_txt,
                target_type=rep.target_type,
                target_id=rep.target_id,
                status=rep.status,
                created_at=created_time
            )
        )

    return PaginatedAdminReportsResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


def get_admin_report_detail(
    report_id: int,
    db: Session
) -> AdminReportDetailResponse:
    """
    Xem chi tiết phiếu tố cáo và nội dung thực tế của đối tượng bị tố cáo:
    - Nếu target_type == 'Product': Load thông tin tin đăng và người bán.
    - Nếu target_type == 'User': Load thông tin hồ sơ và số dư ví của violator.
    - Nếu target_type == 'Comment': Load nội dung bình luận và người bình luận.
    """
    stmt = (
        select(Report)
        .where(Report.report_id == report_id)
        .options(
            selectinload(Report.reason),
            selectinload(Report.user).selectinload(User.profile)
        )
    )
    report = db.scalars(stmt).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Phiếu tố cáo ID {report_id} không tồn tại"
        )

    target_data: Dict[str, Any] = {}
    if report.target_type == "Product":
        prod = db.get(Product, report.target_id)
        if prod:
            target_data = {
                "product_id": prod.product_id,
                "title": prod.title,
                "price": prod.price,
                "status_id": prod.status_id,
                "seller_id": prod.seller_id,
                "is_deleted": bool(prod.deleted_at)
            }
        else:
            target_data = {"error": "Sản phẩm đã bị xóa khỏi hệ thống"}

    elif report.target_type == "User":
        usr = db.get(User, report.target_id)
        if usr:
            target_data = {
                "user_id": usr.id,
                "email": usr.Email,
                "full_name": get_user_display_name(usr),
                "is_active": bool(usr.isActive),
                "role_id": usr.role_id
            }
        else:
            target_data = {"error": "Người dùng không tồn tại"}

    elif report.target_type == "Comment":
        cmt = db.get(Comment, report.target_id)
        if cmt:
            target_data = {
                "comment_id": cmt.comment_id,
                "product_id": cmt.product_id,
                "user_id": cmt.user_id,
                "content": cmt.content
            }
        else:
            target_data = {"error": "Bình luận không tồn tại"}

    reporter_name = get_user_display_name(report.user)
    reporter_email = report.user.Email if report.user else "N/A"
    reason_txt = report.reason.content if report.reason else "Khác"
    created_time = getattr(report, "CreatedAt", datetime.now(timezone.utc))

    return AdminReportDetailResponse(
        report_id=report.report_id,
        reporter_id=report.reporter_id,
        reporter_name=reporter_name,
        reporter_email=reporter_email,
        reason_id=report.reason_id,
        reason_content=reason_txt,
        target_type=report.target_type,
        target_id=report.target_id,
        status=report.status,
        target_data=target_data,
        created_at=created_time
    )


def resolve_user_report(
    report_id: int,
    payload: ReportResolveRequest,
    current_admin: User,
    db: Session
) -> ReportResolveResponse:
    """
    Giải quyết tố cáo vi phạm theo cơ chế linh hoạt thống nhất tại Gate A (Seq 5):
    1. Kiểm tra report đang ở trạng thái 'Pending'.
    2. Cập nhật report.status = 'Resolved'.
    3. Áp dụng chế tài:
       - Nếu ban_user = True: Khóa tài khoản violator (isActive = False), ẩn các tin đang bán.
       - Nếu add_blacklist = True: Lưu Email/SĐT violator vào bảng blacklists.
       - Nếu delete_target = True: Xóa mềm tin đăng vi phạm hoặc xóa bình luận.
    4. Gửi Notification cảm ơn người tố cáo (reporter).
    5. Ghi SystemLog kiểm toán (Resolve_Report / Ban_User).
    6. Cam kết toàn vẹn Transaction (BR-ADM-6).
    """
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Phiếu tố cáo ID {report_id} không tồn tại"
        )

    if report.status != "Pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Phiếu tố cáo này đã được xử lý trước đó với trạng thái '{report.status}'!"
        )

    report.status = "Resolved"
    is_user_banned = False
    is_target_deleted = False

    # Xác định đối tượng vi phạm (violator)
    violator_id: Optional[int] = None
    if report.target_type == "User":
        violator_id = report.target_id
    elif report.target_type == "Product":
        prod = db.get(Product, report.target_id)
        if prod:
            violator_id = prod.seller_id
            if payload.delete_target:
                prod.deleted_at = datetime.now(timezone.utc)
                prod.status_id = 4  # Hidden
                is_target_deleted = True
    elif report.target_type == "Comment":
        cmt = db.get(Comment, report.target_id)
        if cmt:
            violator_id = cmt.user_id
            if payload.delete_target:
                db.delete(cmt)
                is_target_deleted = True

    # Thi hành Khóa tài khoản (Ban User)
    if payload.ban_user and violator_id:
        if violator_id == current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quy tắc an toàn: Quản trị viên không thể tự khóa tài khoản của chính mình!"
            )
        violator = db.get(User, violator_id)
        if violator:
            violator.isActive = False
            is_user_banned = True

            # Ẩn các tin đăng đang Active của người bị khóa
            stmt_hide = (
                select(Product)
                .where(
                    Product.seller_id == violator_id,
                    Product.status_id == 2,
                    Product.deleted_at.is_(None)
                )
            )
            for active_prod in db.scalars(stmt_hide).all():
                active_prod.status_id = 4  # Hidden

            # Thông báo cho người vi phạm
            send_system_notification(
                user_id=violator_id,
                title="Tài khoản của bạn đã bị khóa do vi phạm",
                message=f"Tài khoản của bạn đã bị vô hiệu hóa vì: {payload.action_taken}. Bạn có thể gửi đơn kháng cáo CCCD qua ứng dụng UniMarket.",
                action_link="/identity-verification/appeal",
                db=db
            )

            # Thêm vào danh sách đen nếu có yêu cầu
            if payload.add_blacklist:
                # 1. Thêm Email
                if violator.Email:
                    chk_email = db.scalars(
                        select(Blacklist).where(Blacklist.blocked_value == violator.Email.strip().lower())
                    ).first()
                    if not chk_email:
                        db.add(Blacklist(
                            admin_id=current_admin.id,
                            blocked_value=violator.Email.strip().lower(),
                            reason=f"Tố cáo #{report.report_id}: {payload.action_taken}"
                        ))
                # 2. Thêm Số điện thoại
                if violator.profile and violator.profile.phone_number:
                    chk_phone = db.scalars(
                        select(Blacklist).where(Blacklist.blocked_value == violator.profile.phone_number.strip())
                    ).first()
                    if not chk_phone:
                        db.add(Blacklist(
                            admin_id=current_admin.id,
                            blocked_value=violator.profile.phone_number.strip(),
                            reason=f"Tố cáo #{report.report_id}: {payload.action_taken}"
                        ))

    # Gửi thông báo cảm ơn người gửi tố cáo (reporter)
    send_system_notification(
        user_id=report.reporter_id,
        title="Báo cáo vi phạm của bạn đã được giải quyết",
        message=f"Cảm ơn bạn đã hỗ trợ bảo vệ cộng đồng UniMarket. Báo cáo của bạn về {report.target_type} #{report.target_id} đã được Ban Quản Trị xử lý: {payload.action_taken}.",
        action_link=None,
        db=db
    )

    # Ghi nhận Audit Trail
    log_msg = f"Resolve_Report: ID {report.report_id} - {payload.action_taken} (Ban={is_user_banned}, Del={is_target_deleted})"
    record_system_log(
        admin_id=current_admin.id,
        action=log_msg,
        target_table="reports",
        db=db
    )

    db.commit()
    return ReportResolveResponse(
        report_id=report.report_id,
        status="Resolved",
        action_taken=payload.action_taken,
        is_user_banned=is_user_banned,
        is_target_deleted=is_target_deleted,
        resolved_at=datetime.now(timezone.utc),
        message="Đã xử lý tố cáo thành công và lưu dấu vết kiểm toán"
    )


def dismiss_user_report(
    report_id: int,
    payload: ReportDismissRequest,
    current_admin: User,
    db: Session
) -> ReportDismissResponse:
    """
    Bác bỏ tố cáo sai sự thật hoặc không đủ bằng chứng (Sequence 5 SRS):
    - Cập nhật report.status = 'Dismissed'.
    - Ghi SystemLog kiểm toán (Dismiss_Report).
    """
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Phiếu tố cáo ID {report_id} không tồn tại"
        )

    if report.status != "Pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Phiếu tố cáo này đã được xử lý trước đó với trạng thái '{report.status}'!"
        )

    report.status = "Dismissed"

    # Ghi nhận Audit Trail
    record_system_log(
        admin_id=current_admin.id,
        action=f"Dismiss_Report: ID {report.report_id} - Lý do: {payload.dismiss_reason[:40]}",
        target_table="reports",
        db=db
    )

    db.commit()
    return ReportDismissResponse(
        report_id=report.report_id,
        status="Dismissed",
        dismiss_reason=payload.dismiss_reason,
        dismissed_at=datetime.now(timezone.utc),
        message="Đã bác bỏ tố cáo và lưu vết nhật ký hệ thống"
    )


# ==============================================================================
# 5. SERVICES KHÁNG CÁO DANH TÍNH & MỞ KHÓA TÀI KHOẢN (IDENTITY APPEAL - SEQ 6 SRS)
# ==============================================================================

def _build_appeal_detail_dto(appeal: IdentityVerification) -> AppealDetailResponse:
    """Đóng gói dữ liệu hồ sơ kháng cáo thành DTO AppealDetailResponse chuẩn hóa"""
    user_email = appeal.user.Email if appeal.user else "N/A"
    user_name = get_user_display_name(appeal.user) if appeal.user else "N/A"
    handler_name = get_user_display_name(appeal.handle) if appeal.handle else None
    submit_time = appeal.submit_at or datetime.now(timezone.utc)

    return AppealDetailResponse(
        request_id=appeal.request_id,
        user_id=appeal.user_id,
        user_email=user_email,
        user_name=user_name,
        contact_phone=appeal.contact_phone,
        other_phone=appeal.other_phone,
        cccd_front_url=appeal.cccd_front_url,
        cccd_back_url=appeal.cccd_back_url,
        sim_ownership_url=appeal.sim_ownership_url,
        status=appeal.status or "PENDING",
        note=appeal.note,
        handle_by_id=appeal.handle_by_id,
        handler_name=handler_name,
        submit_at=submit_time
    )


def submit_identity_appeal(
    payload: AppealCreateRequest,
    current_banned_user: User,
    db: Session
) -> MyAppelStatusResponse:
    """
    Người dùng bị khóa nộp hồ sơ kháng cáo CCCD và SIM chính chủ (Sequence 6 SRS):
    - Yêu cầu xác thực tài khoản bị khóa qua dependency `get_current_banned_user`.
    - Kiểm tra nếu người dùng đã có đơn kháng cáo đang ở trạng thái 'PENDING' -> Ném 409 Conflict (BR-ADM-5).
    - Tạo bản ghi mới trong bảng `identity_verification` với `status = 'PENDING'`.
    - Commit và trả về trạng thái tiếp nhận hồ sơ.
    """
    pending_check = db.scalars(
        select(IdentityVerification).where(
            IdentityVerification.user_id == current_banned_user.id,
            IdentityVerification.status == "PENDING"
        )
    ).first()

    if pending_check:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bạn hiện đang có một đơn kháng cáo đang trong quá trình thẩm định. Vui lòng kiên nhẫn chờ Ban Quản Trị phản hồi trước khi gửi đơn mới!"
        )

    now_utc = datetime.now(timezone.utc)
    new_appeal = IdentityVerification(
        user_id=current_banned_user.id,
        handle_by_id=None,
        status="PENDING",
        contact_phone=payload.contact_phone.strip(),
        other_phone=payload.other_phone.strip() if payload.other_phone else None,
        cccd_front_url=payload.cccd_front_url.strip(),
        cccd_back_url=payload.cccd_back_url.strip(),
        sim_ownership_url=payload.sim_ownership_url.strip(),
        note=payload.note.strip() if payload.note else None,
        submit_at=now_utc
    )

    db.add(new_appeal)
    db.commit()
    db.refresh(new_appeal)

    return MyAppelStatusResponse(
        request_id=new_appeal.request_id,
        status="PENDING",
        submit_at=new_appeal.submit_at or now_utc,
        note=new_appeal.note,
        message="Hồ sơ kháng cáo của bạn đã được gửi thành công. Ban Quản Trị UniMarket sẽ đối soát thông tin trong vòng 24-48 giờ làm việc."
    )


def get_my_latest_appeal(
    current_banned_user: User,
    db: Session
) -> MyAppelStatusResponse:
    """
    Người dùng bị khóa tra cứu tình trạng đơn kháng cáo mới nhất của mình (Sequence 6 SRS):
    - Trả về mã đơn, trạng thái xét duyệt và phản hồi/lý do từ Ban Quản Trị.
    """
    stmt = (
        select(IdentityVerification)
        .where(IdentityVerification.user_id == current_banned_user.id)
        .order_by(IdentityVerification.request_id.desc())
    )
    appeal = db.scalars(stmt).first()
    if not appeal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bạn chưa gửi bất kỳ hồ sơ kháng cáo danh tính nào trên hệ thống"
        )

    msg_map = {
        "PENDING": "Hồ sơ của bạn đang được phân công cho Ban Quản Trị thẩm định.",
        "APPROVED": "Hồ sơ kháng cáo đã được phê duyệt! Tài khoản của bạn đã được mở khóa.",
        "REJECTED": "Hồ sơ kháng cáo của bạn đã bị từ chối. Vui lòng xem lý do và nộp lại nếu cần."
    }
    status_str = appeal.status or "PENDING"

    return MyAppelStatusResponse(
        request_id=appeal.request_id,
        status=status_str,
        submit_at=appeal.submit_at or datetime.now(timezone.utc),
        note=appeal.note,
        message=msg_map.get(status_str, "Hồ sơ đang được xử lý.")
    )


def get_pending_appeals_list(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = "PENDING"
) -> PaginatedAppealsResponse:
    """
    Lấy danh sách hàng đợi hồ sơ kháng cáo danh tính dành cho Staff/Admin:
    - Mặc định lọc đơn 'PENDING'. Có thể lọc 'APPROVED', 'REJECTED' hoặc None (tất cả).
    - Hỗ trợ phân trang chuyên nghiệp và nạp trước quan hệ user/profile/handler.
    """
    stmt = (
        select(IdentityVerification)
        .options(
            selectinload(IdentityVerification.user).selectinload(User.profile),
            selectinload(IdentityVerification.handle).selectinload(User.profile)
        )
        .order_by(IdentityVerification.request_id.desc())
    )

    if status_filter:
        stmt = stmt.where(IdentityVerification.status == status_filter)

    count_stmt = select(func.count(IdentityVerification.request_id))
    if status_filter:
        count_stmt = count_stmt.where(IdentityVerification.status == status_filter)
    total = db.scalar(count_stmt) or 0

    offset = (page - 1) * page_size
    appeals = db.scalars(stmt.offset(offset).limit(page_size)).all()

    items = [_build_appeal_detail_dto(a) for a in appeals]

    return PaginatedAppealsResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


def get_appeal_detail(
    request_id: int,
    db: Session
) -> AppealDetailResponse:
    """
    Xem chi tiết hồ sơ kháng cáo kèm ảnh CCCD và ảnh SIM để Admin đối soát:
    - Nạp toàn bộ quan hệ user và admin xử lý.
    """
    stmt = (
        select(IdentityVerification)
        .where(IdentityVerification.request_id == request_id)
        .options(
            selectinload(IdentityVerification.user).selectinload(User.profile),
            selectinload(IdentityVerification.handle).selectinload(User.profile)
        )
    )
    appeal = db.scalars(stmt).first()
    if not appeal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hồ sơ kháng cáo ID {request_id} không tồn tại trên hệ thống"
        )

    return _build_appeal_detail_dto(appeal)


def approve_appeal(
    request_id: int,
    current_admin: User,
    db: Session
) -> AppealApproveResponse:
    """
    Phê duyệt đơn kháng cáo mở khóa tài khoản (Sequence 6 SRS, BR-ADM-5):
    1. Kiểm tra đơn tồn tại và đang ở trạng thái 'PENDING'.
    2. Cập nhật `appeal.status = 'APPROVED'`, gán `appeal.handle_by_id = current_admin.id`.
    3. Mở khóa tài khoản: `user.isActive = True`.
    4. Gỡ bỏ Email và Số điện thoại của người dùng khỏi bảng `blacklists` (nếu có).
    5. Gửi Notification thông báo chúc mừng mở khóa tài khoản.
    6. Ghi SystemLog kiểm toán (Unban_User).
    7. Commit Database Transaction toàn vẹn.
    """
    appeal = db.get(IdentityVerification, request_id)
    if not appeal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hồ sơ kháng cáo ID {request_id} không tồn tại"
        )

    if appeal.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Hồ sơ kháng cáo này đã được xử lý trước đó với trạng thái '{appeal.status}'!"
        )

    now_utc = datetime.now(timezone.utc)
    appeal.status = "APPROVED"
    appeal.handle_by_id = current_admin.id

    # 1. Mở khóa người dùng
    user = db.get(User, appeal.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng ID {appeal.user_id} liên kết với hồ sơ không tồn tại"
        )

    user.isActive = True

    # 2. Xóa khỏi danh sách đen blacklists
    blocked_values_to_clean = []
    if user.Email:
        blocked_values_to_clean.append(user.Email.strip().lower())
    if appeal.contact_phone:
        blocked_values_to_clean.append(appeal.contact_phone.strip())
    if user.profile and user.profile.phone_number:
        blocked_values_to_clean.append(user.profile.phone_number.strip())

    if blocked_values_to_clean:
        stmt_del_bl = (
            select(Blacklist)
            .where(Blacklist.blocked_value.in_(blocked_values_to_clean))
        )
        for bl in db.scalars(stmt_del_bl).all():
            db.delete(bl)

    # 3. Gửi thông báo hệ thống
    send_system_notification(
        user_id=user.id,
        title="Kháng cáo được chấp thuận - Tài khoản đã mở khóa",
        message="Hồ sơ xác minh danh tính và SIM của bạn đã được Ban Quản Trị phê duyệt. Tài khoản của bạn đã được kích hoạt lại bình thường.",
        action_link="/",
        db=db
    )

    # 4. Ghi Audit Trail
    record_system_log(
        admin_id=current_admin.id,
        action=f"Unban_User: Mở khóa User ID {user.id} ({user.Email}) qua hồ sơ kháng cáo #{appeal.request_id}",
        target_table="identity_verification",
        db=db
    )

    db.commit()
    return AppealApproveResponse(
        request_id=appeal.request_id,
        status="APPROVED",
        user_id=user.id,
        is_user_active=True,
        approved_at=now_utc,
        message="Đã phê duyệt kháng cáo, mở khóa tài khoản người dùng và gỡ khỏi danh sách đen thành công"
    )


def reject_appeal(
    request_id: int,
    payload: AppealRejectRequest,
    current_admin: User,
    db: Session
) -> AppealRejectResponse:
    """
    Bác bỏ đơn kháng cáo danh tính (Sequence 6 SRS):
    - Cập nhật `appeal.status = 'REJECTED'`, gán `appeal.handle_by_id = current_admin.id`.
    - Ghi nhận lý do từ chối vào `appeal.note`.
    - Tài khoản vẫn giữ nguyên trạng thái bị khóa (`isActive = False`).
    - Gửi Notification thông báo lý do cho người dùng.
    - Ghi SystemLog kiểm toán (Reject_Appeal).
    """
    appeal = db.get(IdentityVerification, request_id)
    if not appeal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hồ sơ kháng cáo ID {request_id} không tồn tại"
        )

    if appeal.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Hồ sơ kháng cáo này đã được xử lý trước đó với trạng thái '{appeal.status}'!"
        )

    now_utc = datetime.now(timezone.utc)
    appeal.status = "REJECTED"
    appeal.handle_by_id = current_admin.id
    rejection_note = f"[Từ chối bởi Admin #{current_admin.id}]: {payload.reject_reason}"
    appeal.note = f"{appeal.note}\n{rejection_note}" if appeal.note else rejection_note

    # Gửi Notification
    send_system_notification(
        user_id=appeal.user_id,
        title="Đơn kháng cáo tài khoản bị từ chối",
        message=f"Hồ sơ kháng cáo mở khóa tài khoản của bạn đã bị từ chối: {payload.reject_reason}. Vui lòng chuẩn bị lại giấy tờ hợp lệ và gửi lại.",
        action_link="/identity-verification/appeal",
        db=db
    )

    # Ghi Audit Trail
    record_system_log(
        admin_id=current_admin.id,
        action=f"Reject_Appeal: ID {appeal.request_id} (User {appeal.user_id}) - {payload.reject_reason[:40]}",
        target_table="identity_verification",
        db=db
    )

    db.commit()
    return AppealRejectResponse(
        request_id=appeal.request_id,
        status="REJECTED",
        user_id=appeal.user_id,
        reject_reason=payload.reject_reason,
        rejected_at=now_utc,
        message="Đã từ chối đơn kháng cáo và giữ nguyên tình trạng khóa tài khoản"
    )


# ==============================================================================
# 6. SERVICES QUẢN LÝ NGƯỜI DÙNG TOÀN SÀN (USER MANAGEMENT - SRS 1.1)
# ==============================================================================

def _build_admin_user_list_dto(user: User) -> AdminUserListItemResponse:
    """Đóng gói dữ liệu người dùng thành DTO danh sách rút gọn"""
    full_name = get_user_display_name(user)
    avatar = get_user_avatar(user)
    phone = user.profile.phone_number if user.profile else None

    # Role mapping
    role_name = user.role.role_name if user.role else ("Super Admin" if user.role_id == 1 else "Normal User")

    # Xác thực sinh viên
    is_student_verified = False
    if user.role_id == 3:
        is_student_verified = True
    elif user.verification and user.verification.status in ("Approved", "APPROVED"):
        is_student_verified = True

    created_at = getattr(user, "CreatedAt", None)

    return AdminUserListItemResponse(
        user_id=user.id,
        email=user.Email,
        full_name=full_name,
        avatar_url=avatar,
        phone_number=phone,
        role_id=user.role_id,
        role_name=role_name,
        account_type=user.account_type,
        is_active=bool(user.isActive),
        is_verified_student=is_student_verified,
        created_at=created_at
    )


def get_admin_users_list(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    role_id: Optional[int] = None,
    is_active: Optional[bool] = None
) -> PaginatedAdminUsersResponse:
    """
    Tra cứu danh sách người dùng toàn sàn có bộ lọc nâng cao (SRS 1.1):
    - search: Tìm kiếm theo Email, Họ tên (first_name, last_name) hoặc Số điện thoại.
    - role_id: Lọc theo vai trò (1: Super Admin, 2: Normal User, 3: Student, 4: Staff).
    - is_active: Lọc theo trạng thái tài khoản (True: Hoạt động, False: Bị khóa).
    """
    stmt = (
        select(User)
        .options(
            selectinload(User.profile),
            selectinload(User.role),
            selectinload(User.verification)
        )
        .order_by(User.id.desc())
    )

    conditions = []
    if search:
        search_kw = f"%{search.strip()}%"
        conditions.append(
            or_(
                User.Email.ilike(search_kw),
                User.profile.has(userProfile.first_name.ilike(search_kw)),
                User.profile.has(userProfile.last_name.ilike(search_kw)),
                User.profile.has(userProfile.phone_number.ilike(search_kw))
            )
        )

    if role_id is not None:
        conditions.append(User.role_id == role_id)

    if is_active is not None:
        conditions.append(User.isActive == is_active)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    count_stmt = select(func.count(User.id))
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    total = db.scalar(count_stmt) or 0

    offset = (page - 1) * page_size
    users = db.scalars(stmt.offset(offset).limit(page_size)).all()

    items = [_build_admin_user_list_dto(u) for u in users]

    return PaginatedAdminUsersResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


def get_admin_user_detail(
    user_id: int,
    db: Session
) -> AdminUserDetailResponse:
    """
    Xem hồ sơ toàn diện của một người dùng phục vụ quản trị và xử lý vi phạm:
    - Hồ sơ cá nhân (tên, avatar, bio, số điện thoại).
    - Trạng thái tài khoản, vai trò, xác minh sinh viên.
    - Thống kê tin đăng: tổng số tin đăng, tổng số tin đã bán thành công.
    - Lịch sử vi phạm: tổng số lần bị người khác gửi phiếu tố cáo.
    - Điểm đánh giá trung bình từ sàn.
    - Số dư ví tiền hiện tại (Wallet currency).
    """
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.profile),
            selectinload(User.stats),
            selectinload(User.role),
            selectinload(User.verification)
        )
    )
    user = db.scalars(stmt).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng ID {user_id} không tồn tại trên hệ thống"
        )

    # Đếm số tin đăng
    total_products_posted = db.scalar(
        select(func.count(Product.product_id)).where(
            Product.seller_id == user_id,
            Product.deleted_at.is_(None)
        )
    ) or 0

    total_products_sold = db.scalar(
        select(func.count(Product.product_id)).where(
            Product.seller_id == user_id,
            Product.status_id == 3,  # Sold
            Product.deleted_at.is_(None)
        )
    ) or 0

    # Đếm số lượt bị tố cáo (target_type == 'User' or seller of reported product)
    total_reports_received = db.scalar(
        select(func.count(Report.report_id)).where(
            Report.target_type == "User",
            Report.target_id == user_id
        )
    ) or 0

    # Lấy số dư ví (Wallet currency)
    wallet = db.scalars(
        select(Wallet).where(Wallet.user_id == user_id)
    ).first()
    wallet_balance = float(wallet.currency) if wallet and wallet.currency is not None else 0.0

    # Thông tin vai trò & sinh viên
    role_name = user.role.role_name if user.role else ("Super Admin" if user.role_id == 1 else "Normal User")
    is_student_verified = False
    edu_email = None
    if user.verification:
        edu_email = user.verification.edu_email
        if user.verification.status in ("Approved", "APPROVED"):
            is_student_verified = True
    if user.role_id == 3:
        is_student_verified = True

    full_name = get_user_display_name(user)
    avatar = get_user_avatar(user)
    phone = user.profile.phone_number if user.profile else None
    bio = user.profile.bio if user.profile else None
    rating = user.stats.rating_avg if user.stats else 0.0
    created_at = getattr(user, "CreatedAt", None)

    return AdminUserDetailResponse(
        user_id=user.id,
        email=user.Email,
        full_name=full_name,
        avatar_url=avatar,
        phone_number=phone,
        bio=bio,
        role_id=user.role_id,
        role_name=role_name,
        account_type=user.account_type,
        is_active=bool(user.isActive),
        is_verified_student=is_student_verified,
        edu_email=edu_email,
        total_products_posted=total_products_posted,
        total_products_sold=total_products_sold,
        total_reports_received=total_reports_received,
        rating_avg=float(rating),
        wallet_balance=wallet_balance,
        created_at=created_at
    )


def update_user_active_status(
    user_id: int,
    payload: UserStatusUpdateRequest,
    current_admin: User,
    db: Session
) -> Dict[str, Any]:
    """
    Khóa hoặc Mở khóa tài khoản người dùng thủ công (BR-ADM-1, Use Case 2.3):
    - Chặn Admin tự khóa tài khoản của chính mình (Safety rule).
    - Nếu khóa tài khoản (`is_active = False`):
      + Chuyển `user.isActive = False`.
      + Ẩn toàn bộ tin đăng đang Active (`Product.status_id = 4`).
      + Tùy chọn `add_to_blacklist = True`: Thêm Email & SĐT vào bảng `blacklists`.
      + Gửi Notification thông báo lý do và đường dẫn gửi kháng cáo CCCD.
      + Ghi SystemLog kiểm toán (`Ban_User`).
    - Nếu mở khóa tài khoản (`is_active = True`):
      + Chuyển `user.isActive = True`.
      + Tự động gỡ Email & SĐT khỏi `blacklists`.
      + Gửi Notification thông báo mở khóa.
      + Ghi SystemLog kiểm toán (`Unban_User`).
    """
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quy tắc an toàn: Quản trị viên không thể tự thay đổi trạng thái tài khoản của chính mình!"
        )

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng ID {user_id} không tồn tại trên hệ thống"
        )

    action_label = "Khóa tài khoản" if not payload.is_active else "Mở khóa tài khoản"

    if payload.is_active is False:
        user.isActive = False

        # Ẩn các tin đăng đang Active của người bị khóa
        stmt_hide = (
            select(Product)
            .where(
                Product.seller_id == user_id,
                Product.status_id == 2,
                Product.deleted_at.is_(None)
            )
        )
        for active_prod in db.scalars(stmt_hide).all():
            active_prod.status_id = 4  # Hidden

        # Đưa vào danh sách đen nếu có yêu cầu
        if payload.add_to_blacklist:
            if user.Email:
                chk_email = db.scalars(
                    select(Blacklist).where(Blacklist.blocked_value == user.Email.strip().lower())
                ).first()
                if not chk_email:
                    db.add(Blacklist(
                        admin_id=current_admin.id,
                        blocked_value=user.Email.strip().lower(),
                        reason=f"Khóa thủ công: {payload.reason}"
                    ))
            if user.profile and user.profile.phone_number:
                chk_phone = db.scalars(
                    select(Blacklist).where(Blacklist.blocked_value == user.profile.phone_number.strip())
                ).first()
                if not chk_phone:
                    db.add(Blacklist(
                        admin_id=current_admin.id,
                        blocked_value=user.profile.phone_number.strip(),
                        reason=f"Khóa thủ công: {payload.reason}"
                    ))

        # Thông báo cho người dùng
        send_system_notification(
            user_id=user_id,
            title="Tài khoản của bạn đã bị khóa",
            message=f"Tài khoản UniMarket của bạn đã bị khóa bởi Quản trị viên. Lý do: {payload.reason}. Bạn có thể gửi đơn kháng cáo CCCD qua ứng dụng.",
            action_link="/identity-verification/appeal",
            db=db
        )

        record_system_log(
            admin_id=current_admin.id,
            action=f"Ban_User: ID {user.id} ({user.Email}) - Lý do: {payload.reason[:40]} (Blacklist={payload.add_to_blacklist})",
            target_table="user",
            db=db
        )

    else:
        user.isActive = True

        # Tự động dọn dẹp blacklist khi mở khóa
        blocked_values = [user.Email.strip().lower()] if user.Email else []
        if user.profile and user.profile.phone_number:
            blocked_values.append(user.profile.phone_number.strip())

        if blocked_values:
            stmt_clean = select(Blacklist).where(Blacklist.blocked_value.in_(blocked_values))
            for bl in db.scalars(stmt_clean).all():
                db.delete(bl)

        send_system_notification(
            user_id=user_id,
            title="Tài khoản của bạn đã được mở khóa",
            message=f"Ban Quản Trị đã mở khóa tài khoản của bạn: {payload.reason}. Chúc bạn có trải nghiệm mua sắm tuyệt vời tại UniMarket!",
            action_link="/",
            db=db
        )

        record_system_log(
            admin_id=current_admin.id,
            action=f"Unban_User: Mở khóa ID {user.id} ({user.Email}) - Lý do: {payload.reason[:40]}",
            target_table="user",
            db=db
        )

    db.commit()
    return {
        "message": f"Đã thực hiện {action_label} thành công cho người dùng ID {user_id}",
        "user_id": user_id,
        "is_active": user.isActive,
        "updated_at": datetime.now(timezone.utc)
    }


def update_user_role(
    user_id: int,
    payload: UserRoleUpdateRequest,
    current_admin: User,
    db: Session
) -> Dict[str, Any]:
    """
    Phân quyền / hạ quyền nhân viên hoặc người dùng (Chỉ Super Admin - BR-ADM-1):
    - Yêu cầu người gọi phải là Super Admin (`current_admin.role_id == 1`).
    - Không cho phép tự hạ quyền của chính mình để tránh mất quyền quản trị tối cao.
    - Cập nhật `user.role_id = payload.role_id`.
    - Gửi thông báo hệ thống và ghi nhận Audit Trail.
    """
    if current_admin.role_id != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Super Admin mới có quyền thay đổi vai trò tài khoản!"
        )

    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quy tắc an toàn: Bạn không thể tự thay đổi vai trò của chính mình!"
        )

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng ID {user_id} không tồn tại"
        )

    role_record = db.get(Role, payload.role_id)
    if not role_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mã vai trò {payload.role_id} không tồn tại trong danh mục hệ thống"
        )

    old_role_id = user.role_id
    user.role_id = payload.role_id

    # Gửi thông báo
    send_system_notification(
        user_id=user_id,
        title="Vai trò tài khoản được cập nhật",
        message=f"Vai trò tài khoản của bạn trên UniMarket đã được cập nhật thành: {role_record.role_name}.",
        action_link="/",
        db=db
    )

    # Ghi nhận Audit Trail
    record_system_log(
        admin_id=current_admin.id,
        action=f"Update_User_Role: ID {user.id} ({user.Email}) từ Role {old_role_id} -> {role_record.role_name} ({payload.role_id})",
        target_table="user",
        db=db
    )

    db.commit()
    return {
        "message": f"Đã cập nhật vai trò người dùng ID {user_id} thành '{role_record.role_name}' thành công",
        "user_id": user_id,
        "old_role_id": old_role_id,
        "new_role_id": payload.role_id,
        "role_name": role_record.role_name,
        "updated_at": datetime.now(timezone.utc)
    }


# ==============================================================================
# 7. SERVICES QUẢN LÝ DANH SÁCH ĐEN (BLACKLIST MANAGEMENT - SRS 1.1)
# ==============================================================================

def get_blacklist_records(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None
) -> PaginatedBlacklistResponse:
    """
    Tra cứu danh sách đen (Blacklist) các Email và Số điện thoại bị cấm (SRS 1.1):
    - Hỗ trợ tìm kiếm theo chuỗi giá trị bị cấm (blocked_value) hoặc lý do cấm (reason).
    - Nạp quan hệ người tạo (Admin thực hiện chặn).
    """
    stmt = (
        select(Blacklist)
        .options(selectinload(Blacklist.user))
        .order_by(Blacklist.blacklist_id.desc())
    )

    if search:
        kw = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Blacklist.blocked_value.ilike(kw),
                Blacklist.reason.ilike(kw)
            )
        )

    count_stmt = select(func.count(Blacklist.blacklist_id))
    if search:
        kw = f"%{search.strip()}%"
        count_stmt = count_stmt.where(
            or_(
                Blacklist.blocked_value.ilike(kw),
                Blacklist.reason.ilike(kw)
            )
        )
    total = db.scalar(count_stmt) or 0

    offset = (page - 1) * page_size
    records = db.scalars(stmt.offset(offset).limit(page_size)).all()

    items = [
        BlacklistItemResponse(
            blacklist_id=r.blacklist_id,
            admin_id=r.admin_id,
            admin_email=r.user.Email if r.user else None,
            blocked_value=r.blocked_value,
            reason=r.reason
        )
        for r in records
    ]

    return PaginatedBlacklistResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


def create_blacklist_entry(
    payload: BlacklistCreateRequest,
    current_admin: User,
    db: Session
) -> BlacklistItemResponse:
    """
    Thêm thủ công Email hoặc Số điện thoại vào danh sách đen (Blacklist):
    - Chuẩn hóa định danh (lowercase với email, strip khoảng trắng).
    - Kiểm tra nếu định danh đã tồn tại trong danh sách đen -> Ném 409 Conflict.
    - Lưu bản ghi và ghi nhận Audit Trail.
    """
    clean_val = payload.blocked_value.strip().lower()

    existing = db.scalars(
        select(Blacklist).where(Blacklist.blocked_value == clean_val)
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Định danh '{clean_val}' đã tồn tại trong danh sách đen trước đó!"
        )

    new_bl = Blacklist(
        admin_id=current_admin.id,
        blocked_value=clean_val,
        reason=payload.reason.strip()
    )
    db.add(new_bl)

    record_system_log(
        admin_id=current_admin.id,
        action=f"Add_Blacklist: Chặn '{clean_val[:30]}' - Lý do: {payload.reason[:40]}",
        target_table="blacklists",
        db=db
    )

    db.commit()
    db.refresh(new_bl)

    return BlacklistItemResponse(
        blacklist_id=new_bl.blacklist_id,
        admin_id=new_bl.admin_id,
        admin_email=current_admin.Email,
        blocked_value=new_bl.blocked_value,
        reason=new_bl.reason
    )


def remove_from_blacklist(
    blacklist_id: int,
    current_admin: User,
    db: Session
) -> Dict[str, Any]:
    """
    Gỡ bỏ định danh khỏi danh sách đen (Blacklist):
    - Xóa bản ghi khỏi bảng `blacklists`.
    - Ghi nhận Audit Trail (`Remove_Blacklist`).
    """
    record = db.get(Blacklist, blacklist_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mục danh sách đen ID {blacklist_id} không tồn tại"
        )

    removed_val = record.blocked_value
    db.delete(record)

    record_system_log(
        admin_id=current_admin.id,
        action=f"Remove_Blacklist: Gỡ bỏ '{removed_val[:30]}' (Blacklist #{blacklist_id})",
        target_table="blacklists",
        db=db
    )

    db.commit()
    return {
        "message": f"Đã gỡ bỏ '{removed_val}' khỏi danh sách đen thành công",
        "blacklist_id": blacklist_id,
        "removed_value": removed_val
    }


# ==============================================================================
# 8. SERVICES AUDIT LOGS & DASHBOARD METRICS (AUDIT TRAIL & KPIS)
# ==============================================================================

def get_system_logs_list(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    action_filter: Optional[str] = None,
    admin_id: Optional[int] = None,
    target_table: Optional[str] = None
) -> PaginatedSystemLogsResponse:
    """
    Tra cứu nhật ký thao tác kiểm toán hệ thống (Audit Trail - BR-ADM-6):
    - Hỗ trợ lọc theo từ khóa hành động `action_filter`, ID người thực hiện `admin_id`, hoặc bảng dữ liệu `target_table`.
    - Sắp xếp giảm dần theo thời gian (mới nhất lên đầu).
    """
    stmt = (
        select(SystemLog)
        .options(
            selectinload(SystemLog.admin).selectinload(User.profile)
        )
        .order_by(SystemLog.log_id.desc())
    )

    conditions = []
    if action_filter:
        conditions.append(SystemLog.action.ilike(f"%{action_filter.strip()}%"))
    if admin_id is not None:
        conditions.append(SystemLog.admin_id == admin_id)
    if target_table:
        conditions.append(SystemLog.target_table == target_table.strip())

    if conditions:
        stmt = stmt.where(and_(*conditions))

    count_stmt = select(func.count(SystemLog.log_id))
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    total = db.scalar(count_stmt) or 0

    offset = (page - 1) * page_size
    logs = db.scalars(stmt.offset(offset).limit(page_size)).all()

    items = []
    for log in logs:
        admin_name = get_user_display_name(log.admin) if log.admin else "Hệ thống"
        admin_email = log.admin.Email if log.admin else "system@unimarket.vn"
        timestamp = log.timestamp or datetime.now(timezone.utc)

        items.append(
            SystemLogItemResponse(
                log_id=log.log_id,
                admin_id=log.admin_id,
                admin_name=admin_name,
                admin_email=admin_email,
                action=log.action,
                target_table=log.target_table,
                timestamp=timestamp
            )
        )

    return PaginatedSystemLogsResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


def get_admin_dashboard_metrics(db: Session) -> AdminDashboardStatsResponse:
    """
    Tổng hợp chỉ số vận hành & kiểm duyệt toàn sàn UniMarket theo thời gian thực (Dashboard Metrics):
    1. Người dùng: Tổng tài khoản, Tài khoản đang hoạt động, Tài khoản bị khóa, Sinh viên đã xác minh.
    2. Tin đăng: Tổng số tin, Tin chờ duyệt (Pending), Tin đang hiển thị (Active), Tin đã bán (Sold), Tin bị từ chối (Rejected).
    3. Hàng đợi vận hành: Phiếu tố cáo chờ xử lý (Pending Reports), Phiếu đã giải quyết (Resolved Reports), Đơn kháng cáo CCCD chờ duyệt (Pending Appeals).
    """
    # 1. Thống kê người dùng
    total_users = db.scalar(select(func.count(User.id))) or 0
    active_users = db.scalar(select(func.count(User.id)).where(User.isActive == True)) or 0
    banned_users = db.scalar(select(func.count(User.id)).where(User.isActive == False)) or 0
    verified_students = db.scalar(
        select(func.count(User.id)).where(
            or_(
                User.role_id == 3,
                User.verification.has(StudentVerification.status.in_(["Approved", "APPROVED"]))
            )
        )
    ) or 0

    # 2. Thống kê tin đăng
    total_products = db.scalar(
        select(func.count(Product.product_id)).where(Product.deleted_at.is_(None))
    ) or 0
    pending_products = db.scalar(
        select(func.count(Product.product_id)).where(
            Product.status_id == 1,
            Product.deleted_at.is_(None)
        )
    ) or 0
    active_products = db.scalar(
        select(func.count(Product.product_id)).where(
            Product.status_id == 2,
            Product.deleted_at.is_(None)
        )
    ) or 0
    sold_products = db.scalar(
        select(func.count(Product.product_id)).where(
            Product.status_id == 3,
            Product.deleted_at.is_(None)
        )
    ) or 0
    rejected_products = db.scalar(
        select(func.count(Product.product_id)).where(
            Product.status_id == 5,
            Product.deleted_at.is_(None)
        )
    ) or 0

    # 3. Thống kê hàng đợi vận hành
    pending_reports = db.scalar(
        select(func.count(Report.report_id)).where(Report.status == "Pending")
    ) or 0
    resolved_reports = db.scalar(
        select(func.count(Report.report_id)).where(Report.status == "Resolved")
    ) or 0
    pending_appeals = db.scalar(
        select(func.count(IdentityVerification.request_id)).where(
            IdentityVerification.status == "PENDING"
        )
    ) or 0

    return AdminDashboardStatsResponse(
        total_users=total_users,
        active_users=active_users,
        banned_users=banned_users,
        verified_students=verified_students,
        total_products=total_products,
        pending_products=pending_products,
        active_products=active_products,
        sold_products=sold_products,
        rejected_products=rejected_products,
        pending_reports=pending_reports,
        resolved_reports=resolved_reports,
        pending_appeals=pending_appeals
    )
