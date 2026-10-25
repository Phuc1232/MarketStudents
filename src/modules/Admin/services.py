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
    Report, ReportReason, Notification, SystemLog, Blacklist, IdentityVerification, Comment
)
from src.modules.Interaction.services import get_user_display_name, get_user_avatar
from .schemas import (
    ProductApproveResponse, ProductRejectRequest, ProductRejectResponse,
    AdminProductDetailResponse, AdminProductListItemResponse, PaginatedAdminProductsResponse,
    AdminProductImageDto, AdminProductAttributeDto, AdminSellerSummaryDto,
    ReportResolveRequest, ReportResolveResponse, ReportDismissRequest, ReportDismissResponse,
    AdminReportListItemResponse, PaginatedAdminReportsResponse, AdminReportDetailResponse
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
