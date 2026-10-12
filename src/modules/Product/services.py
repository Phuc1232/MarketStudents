from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, and_, or_
from fastapi import HTTPException, status
from datetime import datetime, timezone
from typing import Optional
from src.modules import  (Product, ProductImage, ProductAttribute, ProductStatus,
                            ProductCondition, ProductView, SubCategory, Category,
                            User, Address, MasterDistrict, MasterWard, ProductCreate, ProductUpdate)

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

def get_product_by_id (product_id: int, user_id: int, db: Session):
    stmt =(select(Product).where(Product.product_id==product_id, Product.deleted_at == None).
           options(selectinload(Product.images),
                   selectinload(Product.seller),
                   selectinload(Product.value)))
    product = db.scalars(stmt).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm hoặc tin đăng đã bị xóa"
        )
    try:
        new_view = ProductView(product_id=product_id, user_id=user_id)
        db.add(new_view)
        db.commit()
    except Exception:
        db.rollback()

    return product

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
    # tim kiem tren toan van
    query = select(Product).where(Product.deleted_at == None)
    # ket hop them trang thai san pham (neu co)
    if status_id is not None:
        query = query.where(Product.status_id == status_id)
    # ket hop tim kiem theo tu khoa 
    if keyword is not None:
        kw_pattern = f"%{keyword.strip()}%"
        query = query.where (
            or_(
                Product.title.ilike(kw_pattern),
                Product.description.ilike(kw_pattern)
            )
        )
    # ket hop loc theo khoang gia (neu co)
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)
    # ket hop loc theo danh muc (neu co)
    if sub_category_id is not None:
        query = query.where(Product.sub_category_id == sub_category_id)
    elif category_id is not None:
        query = query.join(SubCategory, Product.sub_category_id == SubCategory.sub_category_id)\
                        .where (SubCategory.category_id == category_id)
    # ket hop loc theo tinh trang san pham (neu co)
    if condition_id is not None:
        query = query.where(Product.condition_id == condition_id)
    # ket hop loc theo dia gioi (neu co)
    if province_id is not None or district_id is not None:
        query = query.join(Address, Address.product_id == Product.product_id)\
                    .join(MasterWard, Address.ward_id == MasterWard.ward_id)
        if district_id is not None:
            query = query.where(MasterWard.district_id == district_id)
        if province_id is not None:
            query = query.join(MasterDistrict, MasterWard.district_id == MasterDistrict.district_id)\
                            .where(MasterDistrict.province_id == province_id)
    # dem ket qua tra ve
    stmt = select(func.count()).select_from(query.subquery())
    total = db.scalar(stmt) or 0
    # phan trang
    offset = (page-1)*page_size
    query = query.order_by(Product.CreatedAt.desc()).offset(offset).limit(page_size)
    items = db.scalars(query).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }

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
    
 