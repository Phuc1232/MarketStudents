from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, and_, or_, case, delete, update
from fastapi import HTTPException, status
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from src.modules import (
    Product, ProductImage, ProductAttribute, ProductStatus,
    ProductCondition, ProductView, SubCategory, Category,
    User, Address, MasterDistrict, MasterWard, ProductCreate, ProductUpdate,
    SavedSearch, ReviewProductConversation, UserSummaryResponse,
    MyPurchaseItemResponse, PaginatedPurchasesResponse,
    ProductSortBy, ToggleVisibilityResponse, TrashProductItemResponse,
    PaginatedTrashResponse, RestoreProductResponse, CleanupTrashResponse,
    Comment, Favorite, Conversation
)
from src.modules.Interaction.services import (
    get_user_display_name, get_user_avatar, process_mark_sold_and_notify_buyer
)

def get_all_product (db: Session):
    return db.scalars(select(Product)).all()

def create_new_product (user_id: int, form: ProductCreate ,db: Session):
    subcat= db.get(SubCategory, form.sub_category_id)
    if not subcat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Danh mục con ID {form.sub_category_id} không tồn tại"
        )
    cond = db.get(ProductCondition, form.condition_id)
    if not cond:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tình trạng sản phẩm ID {form.condition_id} không tồn tại"
        )
    thumb = form.thumbnails
    if not thumb and form.images:
        thumb = form.images[0].image_url
    # Kiểm tra quyền: Super Admin (role_id = 1) được duyệt ngay; User thường bắt buộc qua Tiền kiểm (Pending_Approval)
    user_obj = db.get(User, user_id)
    initial_status_id = 2 if (user_obj and getattr(user_obj, "role_id", None) == 1) else 1

    new_pro = Product(
        seller_id=user_id,
        sub_category_id=form.sub_category_id,
        status_id=initial_status_id,  # 1: Pending_Approval (Tiền kiểm Gate A) | 2: Active (Admin)
        condition_id=form.condition_id,
        title=form.title.strip(),
        price=form.price,
        description=form.description,
        thumbnails=thumb
    )
    db.add(new_pro)
    db.flush()

    for idx, img in enumerate(form.images[:5]):
        is_thumb = img.is_thumbnail or (idx==0 and not any (img.is_thumbnail for i in form.images))
        prod_img = ProductImage(
            product_id=new_pro.product_id,
            image_url=img.image_url,
            display_order=img.display_order if img.display_order else idx,
            is_thumbnail=is_thumb
        )
        db.add(prod_img)
    
    for attr in form.attributes:
        prod_attr = ProductAttribute(
            product_id=new_pro.product_id,
            attribute_id=attr.attribute_id,
            Value_Text=attr.value_text,
            Value_Num=attr.value_num if attr.value_num else ""
        )
        db.add(prod_attr)

    # 6. Lưu địa chỉ giao dịch gắn với sản phẩm (nếu có nhập)
    if form.ward_id and form.specific_address:
        prod_address = Address(
            user_id=user_id,
            product_id=new_pro.product_id,
            ward_id=form.ward_id,
            specific_name=form.specific_address,
            type="Giao dịch",
            is_default=False
        )
        db.add(prod_address)
    db.commit()
    db.refresh(new_pro)
    return get_product_by_id (new_pro.product_id, user_id, db)

def get_product_by_id (product_id: int, user_id: Optional[int] = None, db: Session = None):
    stmt = (
        select(Product)
        .where(Product.product_id == product_id, Product.deleted_at == None)
        .options(
            selectinload(Product.images),
            selectinload(Product.seller),
            selectinload(Product.value).selectinload(ProductAttribute.attribute),
            selectinload(Product.condition),
            selectinload(Product.status)
        )
    )
    product = db.scalars(stmt).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm hoặc tin đăng đã bị xóa"
        )
    return product

def record_product_view_history(product_id: int, user_id: int, db: Session):
    """
    Xử lý lưu lịch sử xem bất đồng bộ có kiểm tra chống trùng lặp (Seq 9).
    Nếu đã tồn tại -> Update viewed_at.
    Nếu chưa tồn tại -> Insert dòng mới.
    """
    product = db.get(Product, product_id)
    if not product or product.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm"
        )

    stmt = select(ProductView).where(
        ProductView.product_id == product_id,
        ProductView.user_id == user_id
    )
    existing_view = db.scalars(stmt).first()

    now_utc = datetime.now(timezone.utc)
    if existing_view:
        existing_view.viewed_at = now_utc
        db.commit()
        return {"message": "Đã cập nhật thời gian xem sản phẩm", "updated": True}
    else:
        new_view = ProductView(
            product_id=product_id,
            user_id=user_id,
            viewed_at=now_utc
        )
        db.add(new_view)
        product.view_count = (product.view_count or 0) + 1
        db.commit()
        return {"message": "Đã ghi nhận lượt xem mới", "created": True}

def search_products(
    keyword: Optional[str] = None,
    category_id: Optional[int] = None,
    sub_category_id: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    condition_id: Optional[int] = None,
    province_id: Optional[int] = None,
    district_id: Optional[int] = None,
    status_id: Optional[int] = 2,  # Mặc định chỉ lấy tin đang Active
    sort_by: ProductSortBy = ProductSortBy.NEWEST,
    page: int = 1,
    page_size: int = 20,
    db: Session = None      
):
    """
    Tìm kiếm và lọc tin đăng nâng cao:
    - Tìm kiếm Tiếng Việt KHÔNG DẤU & CÓ DẤU (PostgreSQL f_unaccent).
    - Hỗ trợ gõ nhầm chính tả / từ khóa gần đúng (PostgreSQL pg_trgm word_similarity).
    - Chấm điểm độ khớp (Relevance Scoring) ưu tiên bài có tiêu đề khớp hoàn toàn hoặc gần đúng.
    - Đa dạng sắp xếp (sort_by: newest, price_asc, price_desc, popular).
    - Lọc khoảng giá, danh mục, quận huyện, tình trạng đồ.
    """
    query = select(Product).where(Product.deleted_at.is_(None))
    
    if status_id is not None:
        query = query.where(Product.status_id == status_id)

    # 1. XỬ LÝ TÌM KIẾM TỪ KHÓA (TIẾNG VIỆT KHÔNG DẤU + FUZZY TYPO TOLERANCE)
    relevance_score_expr = None
    if keyword is not None and keyword.strip():
        clean_kw = keyword.strip()
        
        # Biểu thức SQL xử lý bỏ dấu tiếng Việt và chuyển chữ thường
        unaccent_title = func.f_unaccent(func.lower(Product.title))
        unaccent_desc = func.f_unaccent(func.lower(func.coalesce(Product.description, "")))
        unaccent_kw = func.f_unaccent(func.lower(clean_kw))

        # Điều kiện 1: Khớp chuỗi con không phân biệt hoa thường và không dấu
        pattern_unaccent = func.f_unaccent(func.lower(f"%{clean_kw}%"))
        title_ilike = unaccent_title.ilike(pattern_unaccent)
        desc_ilike = unaccent_desc.ilike(pattern_unaccent)

        # Điều kiện 2: Khớp độ tương đồng từ khóa gần đúng (Fuzzy Typo Tolerance qua pg_trgm)
        trgm_similarity = func.word_similarity(unaccent_kw, unaccent_title)
        fuzzy_match = trgm_similarity >= 0.38

        # Kết hợp điều kiện lọc
        query = query.where(or_(title_ilike, desc_ilike, fuzzy_match))

        # Chấm điểm độ khớp Relevance Score:
        relevance_score_expr = case(
            (unaccent_title.ilike(unaccent_kw), 100.0),
            (title_ilike, 70.0),
            (fuzzy_match, trgm_similarity * 50.0),
            (desc_ilike, 20.0),
            else_=0.0
        )

    # 2. BỘ LỌC KHOẢNG GIÁ
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)

    # 3. BỘ LỌC DANH MỤC
    if sub_category_id is not None:
        query = query.where(Product.sub_category_id == sub_category_id)
    elif category_id is not None:
        query = query.join(SubCategory, Product.sub_category_id == SubCategory.sub_category_id)\
                     .where(SubCategory.category_id == category_id)

    # 4. BỘ LỌC TÌNH TRẠNG SẢN PHẨM
    if condition_id is not None:
        query = query.where(Product.condition_id == condition_id)

    # 5. ƯU TIÊN VỊ TRÍ ĐỊA LÝ (THEO QUẬN/HUYỆN & TỈNH/THÀNH)
    has_location_filter = (province_id is not None or district_id is not None)
    rank_expr = None
    if has_location_filter:
        query = query.outerjoin(Address, Address.product_id == Product.product_id)\
                     .outerjoin(MasterWard, Address.ward_id == MasterWard.ward_id)\
                     .outerjoin(MasterDistrict, MasterWard.district_id == MasterDistrict.district_id)

        if province_id is not None:
            query = query.where(MasterDistrict.province_id == province_id)

        rank_expr = case(
            (MasterWard.district_id == district_id, 2),
            (MasterDistrict.province_id == province_id, 1),
            else_=0
        )

    # 6. SẮP XẾP KẾT QUẢ (SORTING)
    order_clauses = []
    if rank_expr is not None:
        order_clauses.append(rank_expr.desc())

    if relevance_score_expr is not None and sort_by == ProductSortBy.NEWEST:
        order_clauses.append(relevance_score_expr.desc())

    if sort_by == ProductSortBy.PRICE_ASC:
        order_clauses.append(Product.price.asc())
        order_clauses.append(Product.CreatedAt.desc())
    elif sort_by == ProductSortBy.PRICE_DESC:
        order_clauses.append(Product.price.desc())
        order_clauses.append(Product.CreatedAt.desc())
    elif sort_by == ProductSortBy.POPULAR:
        # Sắp xếp theo Counter Cache view_count cực nhanh (O(1) nhờ Index)
        order_clauses.append(Product.view_count.desc())
        order_clauses.append(Product.CreatedAt.desc())
    else:  # ProductSortBy.NEWEST
        order_clauses.append(Product.CreatedAt.desc())

    query = query.order_by(*order_clauses)

    stmt_count = select(func.count()).select_from(query.subquery())
    total = db.scalar(stmt_count) or 0

    offset = (page - 1) * page_size
    items = db.scalars(query.offset(offset).limit(page_size)).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }

def get_popular_search_suggestions(db: Session, limit: int = 8) -> List[str]:
    """
    Lấy danh sách các từ khóa tìm kiếm thịnh hành được quan tâm nhất (Seq 14).
    Ưu tiên lấy các từ khóa được tìm nhiều nhất trong bảng SavedSearch.
    """
    stmt = (
        select(SavedSearch.keyword, func.count(SavedSearch.search_id).label("total_searches"))
        .group_by(SavedSearch.keyword)
        .order_by(func.count(SavedSearch.search_id).desc())
        .limit(limit)
    )
    results = db.execute(stmt).all()
    keywords = [row[0] for row in results if row[0]]

    fallback_defaults = [
        "iPhone 14", "Macbook cũ", "Giáo trình Toán", "Xe máy Wave",
        "Tủ lạnh mini", "Bàn học gấp", "Máy tính Casio", "Màn hình 24 inch"
    ]
    for kw in fallback_defaults:
        if len(keywords) >= limit:
            break
        if kw not in keywords:
            keywords.append(kw)

    return keywords

def get_my_product (user_id: int, db: Session):
    stmt = select(Product).where(Product.seller_id == user_id, Product.deleted_at == None)\
                        .order_by(Product.CreatedAt.desc())
    return db.scalars(stmt).all()

def update_my_product (product_id: int, user_id: int, form: ProductUpdate, db: Session):
    product = db.get(Product, product_id)
    if not product or product.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm"
        )
    if product.seller_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền chỉnh sửa tin đăng của người khác!"
        )
    for field, value in form.model_dump(exclude_unset=True).items():
        setattr(product,field,value)
    db.commit()
    db.refresh(product)
    return get_product_by_id(product.product_id,user_id,db)

async def mark_product_as_sold(product_id: int, user_id: int, buyer_id: Optional[int], db: Session):
    """
    Đánh dấu tin đăng là đã bán (Sold), cập nhật người mua và tự động kích hoạt luồng mời đánh giá (Seq 7).
    Tích hợp trọn vẹn cập nhật DB, sinh thông báo Notification và đẩy Real-time WebSocket cho người mua.
    """
    return await process_mark_sold_and_notify_buyer(
        product_id=product_id,
        seller_id=user_id,
        buyer_id=buyer_id,
        db=db
    )

def soft_delete_product(product_id: int, user_id: int, db: Session):
    """
    Xóa mềm tin đăng (lưu thùng rác trong vòng 30 ngày) -> AC-12, BR-7.
    """
    product = db.get(Product, product_id)
    if not product or product.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm"
        )

    if product.seller_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xóa tin đăng của người khác!"
        )

    product.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Đã xóa tin đăng thành công (tin được lưu trong thùng rác 30 ngày)."}


# ==============================================================================
# MY PURCHASES SERVICES (SEQ 7 - PHASE 2 EXTENSION)
# ==============================================================================

def get_my_purchased_products(
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    db: Session = None
) -> PaginatedPurchasesResponse:
    """
    Lấy danh sách các sản phẩm mà người dùng hiện tại đã mua thành công (buyer_id == user_id).
    Tự động đối chiếu bảng Review để kiểm tra cờ has_reviewed (Seq 7).
    """
    # 1. Query danh sách sản phẩm đã mua
    stmt_base = (
        select(Product)
        .options(
            selectinload(Product.seller).selectinload(User.profile),
            selectinload(Product.images),
            selectinload(Product.condition)
        )
        .where(
            Product.buyer_id == user_id,
            Product.deleted_at.is_(None)
        )
        .order_by(Product.UpdateAt.desc())
    )

    # 2. Đếm tổng số
    stmt_count = select(func.count()).select_from(Product).where(
        Product.buyer_id == user_id,
        Product.deleted_at.is_(None)
    )
    total = db.scalar(stmt_count) or 0

    # 3. Phân trang
    offset = (page - 1) * page_size
    products = db.scalars(stmt_base.offset(offset).limit(page_size)).all()

    # 4. Lấy tập hợp các product_id mà user_id này đã từng gửi đánh giá
    product_ids = [p.product_id for p in products]
    reviewed_product_ids = set()
    if product_ids:
        stmt_reviews = select(ReviewProductConversation.product_id).where(
            ReviewProductConversation.reviewer_id == user_id,
            ReviewProductConversation.product_id.in_(product_ids)
        )
        reviewed_product_ids = set(db.scalars(stmt_reviews).all())

    # 5. Đóng gói DTO
    items: List[MyPurchaseItemResponse] = []
    for prod in products:
        seller_obj = prod.seller
        seller_dto = UserSummaryResponse(
            user_id=seller_obj.id,
            full_name=get_user_display_name(seller_obj),
            avatar_url=get_user_avatar(seller_obj)
        )

        thumb = prod.thumbnails
        if not thumb and prod.images:
            thumb = prod.images[0].image_url

        cond_name = prod.condition.condition_name if prod.condition else None
        purchased_time = getattr(prod, 'UpdateAt', getattr(prod, 'updated_at', datetime.now(timezone.utc)))

        items.append(
            MyPurchaseItemResponse(
                product_id=prod.product_id,
                title=prod.title,
                price=prod.price,
                thumbnail_url=thumb,
                condition_name=cond_name,
                seller=seller_dto,
                purchased_at=purchased_time,
                has_reviewed=(prod.product_id in reviewed_product_ids)
            )
        )

    return PaginatedPurchasesResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


# ==============================================================================
# PRODUCT LIFECYCLE & TRASH SERVICES (AC-12, BR-7)
# ==============================================================================
# CẤU HÌNH THỜI HẠN BẢO LƯU THÙNG RÁC (QUY TẮC BR-7, AC-12):
# - Mặc định Sản xuất: 30 ngày (30 * 86400 giây).
TRASH_EXPIRATION_SECONDS = 30 * 86400  # 30 ngày


def toggle_product_visibility(product_id: int, user_id: int, db: Session) -> ToggleVisibilityResponse:
    """
    Nghiệp vụ: Người bán chủ động bấm 'Tạm ẩn tin' khi bận/hết hàng và 'Mở lại tin' khi sẵn sàng.
    - Status 2 (Active)   -> Chuyển thành Status 4 (Hidden)
    - Status 4 (Hidden)   -> Chuyển thành Status 2 (Active)
    - Các trạng thái khác (Pending=1, Sold=3, Rejected=5) không được phép tự do chuyển đổi.
    """
    product = db.get(Product, product_id)
    if not product or product.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm hoặc sản phẩm đang nằm trong thùng rác!"
        )

    if product.seller_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thay đổi trạng thái tin đăng của người khác!"
        )

    if product.status_id == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tin đăng đang ở trạng thái 'Chờ duyệt' (Pending Approval), không thể ẩn/mở lại!"
        )
    elif product.status_id == 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tin đăng đã được đánh dấu 'Đã bán' (Sold). Vui lòng không thay đổi trạng thái!"
        )
    elif product.status_id == 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tin đăng đã bị Quản trị viên 'Từ chối' (Rejected). Không thể tự mở lại!"
        )

    if product.status_id == 2:
        product.status_id = 4
        status_name = "Hidden"
        msg = "Đã tạm ẩn tin đăng thành công. Tin sẽ không xuất hiện trên bảng tìm kiếm công khai."
    elif product.status_id == 4:
        product.status_id = 2
        status_name = "Active"
        msg = "Đã mở lại tin đăng thành công. Sản phẩm hiện đã hiển thị công khai cho mọi người mua."
    else:
        product.status_id = 4
        status_name = "Hidden"
        msg = "Đã cập nhật trạng thái tin sang Tạm ẩn."

    db.commit()
    db.refresh(product)

    return ToggleVisibilityResponse(
        product_id=product.product_id,
        status_id=product.status_id,
        status_name=status_name,
        message=msg
    )


def get_my_trash_products(
    user_id: int, 
    page: int = 1, 
    page_size: int = 20, 
    db: Session = None
) -> PaginatedTrashResponse:
    """
    Nghiệp vụ: Người bán xem danh sách 'Thùng rác của tôi' (/product/me/trash).
    Tự động tính toán số ngày còn lại (remaining_days) trước khi bị xóa vĩnh viễn (BR-7: 30 ngày).
    """
    stmt_base = (
        select(Product)
        .where(
            Product.seller_id == user_id,
            Product.deleted_at.is_not(None)
        )
        .order_by(Product.deleted_at.desc())
    )

    stmt_count = select(func.count(Product.product_id)).where(
        Product.seller_id == user_id,
        Product.deleted_at.is_not(None)
    )
    total = db.scalar(stmt_count) or 0

    offset = (page - 1) * page_size
    products = db.scalars(stmt_base.offset(offset).limit(page_size)).all()

    now_utc = datetime.now(timezone.utc)
    items: List[TrashProductItemResponse] = []

    for p in products:
        del_at = p.deleted_at
        if del_at.tzinfo is None:
            del_at = del_at.replace(tzinfo=timezone.utc)

        elapsed_seconds = (now_utc - del_at).total_seconds()
        rem_sec = max(0, int(TRASH_EXPIRATION_SECONDS - elapsed_seconds))
        can_restore = rem_sec > 0
        rem_days = int(rem_sec // 86400) if rem_sec >= 86400 else (1 if can_restore else 0)

        thumb = p.thumbnails
        if not thumb and p.images:
            thumb = p.images[0].image_url

        items.append(
            TrashProductItemResponse(
                product_id=p.product_id,
                title=p.title,
                price=p.price,
                thumbnails=thumb,
                sub_category_id=p.sub_category_id,
                condition_id=p.condition_id,
                status_id=p.status_id,
                deleted_at=del_at,
                remaining_days=rem_days,
                remaining_seconds=rem_sec,
                can_restore=can_restore
            )
        )

    return PaginatedTrashResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


def restore_soft_deleted_product(
    product_id: int, 
    user_id: int, 
    db: Session
) -> RestoreProductResponse:
    """
    Nghiệp vụ: Khôi phục tin đăng trước hạn 30 ngày (BR-7).
    - Xóa cờ deleted_at (gán None).
    - Đưa trạng thái về:
        + Nếu trước đó là Sold (3): Giữ nguyên Sold.
        + Mặc định: Đưa về Active (2).
    """
    product = db.get(Product, product_id)
    if not product or product.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tin đăng không tồn tại trong thùng rác!"
        )

    if product.seller_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền khôi phục tin đăng của người khác!"
        )

    del_at = product.deleted_at
    if del_at.tzinfo is None:
        del_at = del_at.replace(tzinfo=timezone.utc)

    now_utc = datetime.now(timezone.utc)
    elapsed_seconds = (now_utc - del_at).total_seconds()
    if elapsed_seconds > TRASH_EXPIRATION_SECONDS:
        limit_desc = f"{TRASH_EXPIRATION_SECONDS // 60} phút (chế độ test)" if TRASH_EXPIRATION_SECONDS < 86400 else "30 ngày (BR-7)"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tin đăng đã nằm trong thùng rác quá thời hạn {limit_desc} và đã hết hạn khôi phục!"
        )

    product.deleted_at = None
    if product.status_id not in [2, 3]:
        product.status_id = 2

    db.commit()
    db.refresh(product)

    return RestoreProductResponse(
        product_id=product.product_id,
        status_id=product.status_id,
        message="Khôi phục tin đăng từ thùng rác thành công! Tin đăng hiện đã hiển thị trở lại."
    )


def hard_delete_single_product(product: Product, db: Session):
    """
    Hàm phụ trợ dọn dẹp sạch sẽ toàn bộ các quan hệ con liên quan tới Product
    trước khi xóa bản ghi cha để tránh lỗi Foreign Key Constraint.
    """
    pid = product.product_id

    # Gỡ liên kết sản phẩm trong hội thoại để giữ nguyên lịch sử chat của người dùng
    db.execute(update(Conversation).where(Conversation.product_id == pid).values(product_id=None))

    # Xóa ảnh sản phẩm
    db.execute(delete(ProductImage).where(ProductImage.product_id == pid))

    # Xóa thuộc tính kỹ thuật động EAV
    db.execute(delete(ProductAttribute).where(ProductAttribute.product_id == pid))

    # Xóa lịch sử lượt xem
    db.execute(delete(ProductView).where(ProductView.product_id == pid))

    # Xóa danh sách yêu thích
    db.execute(delete(Favorite).where(Favorite.product_id == pid))

    # Xóa địa chỉ gắn với sản phẩm
    db.execute(delete(Address).where(Address.product_id == pid))

    # Xóa bình luận liên quan
    db.execute(delete(Comment).where(Comment.product_id == pid))

    # Xóa đánh giá giao dịch nếu có
    db.execute(delete(ReviewProductConversation).where(ReviewProductConversation.product_id == pid))

    # Xóa chính bản ghi Product
    db.delete(product)


def permanently_delete_product(
    product_id: int, 
    user_id: int, 
    db: Session
) -> Dict[str, Any]:
    """
    Nghiệp vụ: Người bán chủ động bấm 'Xóa vĩnh viễn' tin đang nằm trong thùng rác.
    """
    product = db.get(Product, product_id)
    if not product or product.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tin đăng không tồn tại trong thùng rác!"
        )

    if product.seller_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thao tác trên tin đăng của người khác!"
        )

    hard_delete_single_product(product=product, db=db)
    db.commit()

    return {
        "product_id": product_id,
        "message": "Đã xóa vĩnh viễn tin đăng và toàn bộ dữ liệu hình ảnh, thuộc tính liên quan."
    }


def cleanup_expired_trash_products(
    db: Session, 
    expired_seconds: Optional[int] = None,
    expired_days: Optional[int] = None
) -> CleanupTrashResponse:
    """
    Nghiệp vụ BR-7: Hàm định kỳ (Cron Job / Worker) quét và dọn dẹp triệt để 
    toàn bộ các tin đăng đã bị xóa mềm quá thời hạn (mặc định 2 phút khi test, 30 ngày khi production).
    """
    if expired_seconds is None:
        if expired_days is not None:
            if TRASH_EXPIRATION_SECONDS < 86400:
                expired_seconds = TRASH_EXPIRATION_SECONDS
            else:
                expired_seconds = expired_days * 86400
        else:
            expired_seconds = TRASH_EXPIRATION_SECONDS

    threshold_time = datetime.now(timezone.utc) - timedelta(seconds=expired_seconds)

    stmt = select(Product).where(
        Product.deleted_at.is_not(None),
        Product.deleted_at <= threshold_time
    )
    expired_products = db.scalars(stmt).all()

    cleaned_ids: List[int] = []
    for prod in expired_products:
        cleaned_ids.append(prod.product_id)
        hard_delete_single_product(product=prod, db=db)

    db.commit()

    limit_desc = f"{expired_seconds // 60} phút" if expired_seconds < 86400 else f"{expired_seconds // 86400} ngày"
    return CleanupTrashResponse(
        cleaned_products_count=len(cleaned_ids),
        cleaned_product_ids=cleaned_ids,
        message=f"Đã dọn dẹp tự động thành công {len(cleaned_ids)} tin đăng quá hạn {limit_desc}."
    )
