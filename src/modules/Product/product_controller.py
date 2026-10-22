from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from src.api.deps import get_db
from src.modules.User.service import get_current_user
from src.modules import(User, ProductCreate, ProductUpdate, ProductDetailResponse,
    ProductListItemResponse, PaginatedProductsResponse, PaginatedPurchasesResponse)
from .services import (
    get_product_by_id, create_new_product, search_products, 
    get_my_product, update_my_product, mark_product_as_sold,
    soft_delete_product, get_all_product,
    record_product_view_history, get_popular_search_suggestions,
    get_my_purchased_products
)


router = APIRouter(
    prefix="/product",
    tags=["Product"]
)
@router.get("/all", response_model=List[ProductDetailResponse], status_code = status.HTTP_200_OK)
def get_all(db: Session = Depends(get_db)):
    return get_all_product(db)
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

@router.get("/search/suggestions", response_model=List[str], status_code=status.HTTP_200_OK)
def search_suggestions(db: Session = Depends(get_db)):
    """
    Lấy danh sách từ khóa tìm kiếm thịnh hành / gợi ý (Seq 14 - Giai đoạn 1).
    Endpoint công khai (Public) phục vụ render thanh dropdown tìm kiếm.
    """
    return get_popular_search_suggestions(db=db)

@router.get(
    "/my-purchases",
    response_model=PaginatedPurchasesResponse,
    status_code=status.HTTP_200_OK,
    summary="Xem lịch sử các sản phẩm tôi đã mua thành công kèm trạng thái đánh giá (Seq 7)"
)
def get_my_purchases(
    page: int = Query(1, ge=1, description="Số trang hiện tại"),
    page_size: int = Query(20, ge=1, le=100, description="Số tin mỗi trang"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Phục vụ màn hình 'Đơn mua của tôi' dành cho Người mua.
    Trả về cờ `has_reviewed`:
    - Nếu false: Frontend hiển thị nút '⭐ Đánh giá người bán' (kết nối trực tiếp Bước 2 của Seq 7).
    - Nếu true: Hiển thị nhãn 'Đã đánh giá'.
    """
    return get_my_purchased_products(
        user_id=user.id,
        page=page,
        page_size=page_size,
        db=db
    )

@router.get("/{product_id}", response_model=ProductDetailResponse, status_code=status.HTTP_200_OK)
def get_this_product (product_id: int, db: Session = Depends(get_db)):
    return get_product_by_id(product_id=product_id, db=db)

@router.post("/{product_id}/view-history", status_code=status.HTTP_200_OK)
def track_product_view(
    product_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    API chạy ngầm (Async) lưu lịch sử xem sản phẩm của người dùng đã đăng nhập (Seq 9).
    Frontend gọi API này sau khi đã render xong giao diện trang chi tiết.
    """
    return record_product_view_history(product_id, user.id, db)

@router.put("/{product_id}/me", response_model=ProductDetailResponse, status_code=status.HTTP_200_OK)
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
