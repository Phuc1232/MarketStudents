from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, and_, or_, case
from fastapi import HTTPException, status
from datetime import datetime, timezone
from typing import Optional, List
from src.modules import (
    Product, ProductImage, ProductAttribute, ProductStatus,
    ProductCondition, ProductView, SubCategory, Category,
    User, Address, MasterDistrict, MasterWard, ProductCreate, ProductUpdate,
    SavedSearch, ReviewProductConversation, UserSummaryResponse,
    MyPurchaseItemResponse, PaginatedPurchasesResponse
)
from src.modules.Interaction.services import get_user_display_name, get_user_avatar

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
    new_pro = Product(
        seller_id=user_id,
        sub_category_id=form.sub_category_id,
        status_id=2,  # Active
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
        db.commit()
        return {"message": "Đã ghi nhận lượt xem mới", "created": True}

def search_products (
    keyword: Optional[str] = None,
    category_id: Optional[int] = None,
    sub_category_id: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    condition_id: Optional[int] = None,
    province_id: Optional[int] = None,
    district_id: Optional[int] = None,
    status_id: Optional[int] = 2,  # Mặc định chỉ lấy tin đang Active
    page: int = 1,
    page_size: int = 20,
    db: Session = None      
    ):
    query = select(Product).where(Product.deleted_at == None)
    if status_id is not None:
        query = query.where(Product.status_id == status_id)
    if keyword is not None:
        kw_pattern = f"%{keyword.strip()}%"
        query = query.where (
            or_(
                Product.title.ilike(kw_pattern),
                Product.description.ilike(kw_pattern)
            )
        )
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)
    if sub_category_id is not None:
        query = query.where(Product.sub_category_id == sub_category_id)
    elif category_id is not None:
        query = query.join(SubCategory, Product.sub_category_id == SubCategory.sub_category_id)\
                        .where (SubCategory.category_id == category_id)
    if condition_id is not None:
        query = query.where(Product.condition_id == condition_id)

    # Ưu tiên vị trí địa lý theo Seq 13
    has_location_filter = (province_id is not None or district_id is not None)
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
        query = query.order_by(rank_expr.desc(), Product.CreatedAt.desc())
    else:
        query = query.order_by(Product.CreatedAt.desc())

    stmt_count = select(func.count()).select_from(query.subquery())
    total = db.scalar(stmt_count) or 0

    offset = (page-1)*page_size
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

def mark_product_as_sold (product_id: int, user_id: int, buyer_id: Optional[int], db: Session):
    product = db.get(Product,product_id)
    if not product or product.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy sản phẩm")
    if (product.seller_id != user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thay đổi trạng thái của tin đăng này!"
        )
    product.status_id = 3
    if buyer_id:
        product.buyer_id = buyer_id
    db.commit()
    return {
        "message": "Đã cập nhật trạng thái tin đăng thành 'ĐÃ BÁN'. Tin đã được ẩn khỏi danh sách tìm kiếm chung.",
        "product_id": product_id,
        "status": "Sold"
    }

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