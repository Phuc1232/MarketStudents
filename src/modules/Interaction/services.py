from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, and_
from fastapi import HTTPException, status
from typing import Optional, List
from datetime import datetime
from src.modules import  (
    FavoriteToggleResponse,
    FavoriteStatusResponse,
    FavoriteProductItemResponse,
    PaginatedFavoritesResponse,
    Product, ProductImage, ProductCondition,
    Favorite,
    User, userProfile
)

def get_user_display_name (user: Optional[User]):
    if not user:
        return "Người dùng ẩn danh"
    if user.profile:
        full = f"{user.profile.last_name or ''} {user.profile.first_name or ''}".strip()
        if full:
            return full
    if user.Email:
        return user.Email.split("@")[0]
    return f"User #{user.id}"

def get_user_avatar(user: Optional[User]) -> Optional[str]:
    """Trả về URL ảnh đại diện của người dùng nếu có."""
    if user and user.profile and user.profile.avatar_url:
        return user.profile.avatar_url
    return None

def get_product_thumbnails (product: Product):
    if product.thumbnails:
        return product.thumbnails
    if product.images:
        for img in product.images:
            if img.is_thumnail:
                return img.image_url
        return product.images[0].image_url
    return None

def toggle_favorite_product (user_id: int, product_id: int, db: Session):
    stmt = select(Product).where(Product.product_id == product_id, Product.deleted_at == None)
    product = db.scalars(stmt).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm ID {product_id} không tồn tại hoặc đã bị xóa."
        )
    if product.seller_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn không thể tự thả tim tin đăng của chính mình."
        )
    exsiting_favorite = db.get(Favorite, (user_id,product_id))
    if exsiting_favorite:
        db.delete(exsiting_favorite)
        db.commit()
        is_favorite = False
        Message = "Đã xoá sản phẩm khỏi mục yêu thích"
    else:
        favorites = Favorite(user_id = user_id, product_id = product_id)
        db.add(favorites)
        db.commit()
        is_favorite = True
        Message = "Đã thêm sản phẩm vào mục yêu thích"
    stmt = select(func.count()).select_from(Favorite).where(Favorite.product_id == product_id)
    total_fav = db.scalar(stmt) or 0
    return FavoriteToggleResponse(
        product_id= product_id,
        is_favorited= is_favorite,
        message= Message,
        total_favorites=total_fav
    )