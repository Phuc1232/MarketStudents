from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from src.api.deps import get_db
from src.modules.User.service import get_current_user
from src.modules import (
    User,
    FavoriteToggleResponse,
    FavoriteStatusResponse,
    PaginatedFavoritesResponse,

)
from src.modules.Interaction.services import (
    toggle_favorite_product
)

router = APIRouter(
    prefix="/interaction",
    tags=["Interaction"]
)

@router.post("/product/{product_id}/favorite", 
            response_model=FavoriteToggleResponse,
            summary="Thả tim hoặc Bỏ thả tim một sản phẩm (Wishlist Toggle)"
)
def toggle_favorite (product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return toggle_favorite_product(user.id,product_id,db)