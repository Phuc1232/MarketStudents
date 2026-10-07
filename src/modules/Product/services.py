from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, and_, or_
from fastapi import HTTPException, status
from datetime import datetime, timezone
from typing import Optional
from src.modules import  (Product, ProductImage, ProductAttribute, ProductStatus,
                            ProductCondition, ProductView, SubCategory, Category,
                            User, Address, MasterDistrict, MasterWard, ProductCreate, ProductUpdate)


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

    

