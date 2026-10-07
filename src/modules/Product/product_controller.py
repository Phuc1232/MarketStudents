from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from src.api.deps import get_db
from src.modules.User.service import get_current_user
from src.modules import(User, ProductCreate, ProductUpdate, ProductDetailResponse,
    ProductListItemResponse, PaginatedProductsResponse)
from .services import (
    get_product_by_id, create_new_product
)


router = APIRouter(
    prefix="/product",
    tags=["Product"]
)
@router.post("", response_model= ProductDetailResponse, status_code=status.HTTP_200_OK)
def post_product (form: ProductCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return create_new_product(user.id, form,db)