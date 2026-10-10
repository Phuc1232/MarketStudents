from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from src.api.deps import get_db
from src.modules.User.service import get_current_user
from src.modules import(User, ProductCreate, ProductUpdate, ProductDetailResponse,
    ProductListItemResponse, PaginatedProductsResponse)
from .services import (
    get_product_by_id, create_new_product, search_products, 
    get_my_product, update_my_product, mark_product_as_sold,
    get_product_by_id, soft_delete_product
)


router = APIRouter(
    prefix="/product",
    tags=["Product"]
)
@router.post("", response_model= ProductDetailResponse, status_code=status.HTTP_200_OK)
def post_product (form: ProductCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return create_new_product(user.id, form,db)

@router.get("", response_model=PaginatedProductsResponse, status_code=status.HTTP_200_OK)
def list_products(
    keyword: Optional[str] = Query(None, description="Từ khóa tìm kiếm theo tên hoặc mô tả"),
    category_id: Optional[int] = Query(None, description="Lọc theo ID danh mục chính"),
    sub_category_id: Optional[int] = Query(None, description="Lọc theo ID danh mục con"),
    min_price: Optional[float] = Query(None, ge=0, description="Giá thấp nhất (VNĐ)"),
    max_price: Optional[float] = Query(None, ge=0, description="Giá cao nhất (VNĐ)"),
    condition_id: Optional[int] = Query(None, description="Tình trạng đồ (1=Mới 100%, 2=Như mới 99%, 3=Đã dùng)"),
    province_id: Optional[int] = Query(None, description="Lọc theo Tỉnh/Thành phố (vd: 79 cho TP.HCM)"),
    district_id: Optional[int] = Query(None, description="Lọc theo Quận/Huyện (vd: 769 cho TP. Thủ Đức)"),
    page: int = Query(1, ge=1, description="Số trang hiện tại"),
    page_size: int = Query(20, ge=1, le=100, description="Số tin hiển thị mỗi trang"),
    db: Session = Depends(get_db)
):
    """
    Tìm kiếm và lọc tin đăng kết hợp nhiều điều kiện (từ khóa, khoảng giá, danh mục, địa điểm, tình trạng).
    """
    return search_products(
        keyword=keyword,
        category_id=category_id,
        sub_category_id=sub_category_id,
        min_price=min_price,
        max_price=max_price,
        condition_id=condition_id,
        province_id=province_id,
        district_id=district_id,
        page=page,
        page_size=page_size,
        db=db
    )

@router.get ("/me", response_model= List[ProductListItemResponse], status_code = status.HTTP_200_OK)
def get_product (user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_my_product(user.id,db)

@router.get("/{product_id}", response_model= ProductListItemResponse, status_code=status.HTTP_200_OK)
def get_this_product (product_id: int, viewer_id: int = None, db: Session = Depends(get_db)):
    return get_product_by_id(product_id,viewer_id,db)

@router.put("/{product_id}/me", response_model= ProductListItemResponse, status_code=status.HTTP_200_OK)
def update_product (product_id: int, form: ProductUpdate,  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return update_my_product(product_id, user.id,form,db)

@router.patch("/{product_id}/sold", status_code = status.HTTP_200_OK)
def sold_product (product_id: int, buyer_id: Optional[int] = Query(None, description="ID người mua nếu có"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return mark_product_as_sold(product_id,user.id,buyer_id,db)

@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
def remove_product(
    product_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Xóa mềm tin đăng (lưu trữ trong thùng rác 30 ngày trước khi dọn dẹp vĩnh viễn).
    """
    return soft_delete_product(product_id, user.id, db)
