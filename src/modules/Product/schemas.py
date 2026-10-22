from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class ProductAttributeValueInput(BaseModel):
    attribute_id: int = Field(..., description="ID thuộc tính từ bảng attributes")
    value_text: Optional[str] = Field(None, description="Giá trị văn bản (vd: 16 GB, Intel i5)")
    value_num: str = Field(default="", description="Giá trị số nếu có (vd: 16)")

class ProductAttributeValueResponse(BaseModel):
    id: int
    attribute_id: int
    Value_Text: Optional[str] = None
    Value_Num: str

    model_config = ConfigDict(from_attributes=True)

# --- 2. HÌNH ẢNH SẢN PHẨM (IMAGES) ---
class ProductImageInput(BaseModel):
    image_url: str = Field(..., description="Đường dẫn URL ảnh sản phẩm")
    display_order: int = Field(default=0, description="Thứ tự hiển thị ảnh")
    is_thumbnail: bool = Field(default=False, description="Đánh dấu là ảnh bìa đại diện")

class ProductImageResponse(BaseModel):
    image_id: int
    image_url: str
    display_order: int
    is_thumbnail: bool

    model_config = ConfigDict(from_attributes=True)

# --- 3. ĐĂNG TIN & SỬA TIN (CREATE / UPDATE) ---
class ProductCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=255, description="Tiêu đề tin đăng bán")
    price: float = Field(..., ge=0, description="Giá bán sản phẩm VNĐ (>= 0)")
    description: Optional[str] = Field(None, description="Mô tả chi tiết sản phẩm")
    thumbnails: Optional[str] = Field(None, description="Ảnh đại diện (nếu không nhập sẽ lấy ảnh đầu tiên)")
    sub_category_id: int = Field(..., description="ID danh mục con (vd: 4 cho Laptop)")
    condition_id: int = Field(..., description="ID tình trạng (vd: 1=Mới, 2=Như mới, 3=Đã dùng)")
    
    # Địa chỉ giao dịch của món hàng (tùy chọn)
    ward_id: Optional[int] = Field(None, description="ID Phường/Xã nơi giao dịch")
    specific_address: Optional[str] = Field(None, description="Địa chỉ cụ thể (vd: KTX Khu B, Trường UTE)")

    # Giới hạn tối đa 5 ảnh đính kèm theo đúng đặc tả SRS (BR-3, AC-8)
    images: List[ProductImageInput] = Field(
        default=[], 
        min_length=1,
        max_length=5, 
        description="Danh sách ảnh đính kèm (tối đa 5 ảnh)"
    )
    
    # Danh sách thuộc tính kỹ thuật động EAV
    attributes: List[ProductAttributeValueInput] = Field(
        default=[], 
        description="Thông số kỹ thuật động (RAM, SSD, Chuyên ngành...)"
    )

class ProductUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=255)
    price: Optional[float] = Field(None, ge=0)
    description: Optional[str] = None
    thumbnails: Optional[str] = None
    condition_id: Optional[int] = None
    status_id: Optional[int] = None

# --- 4. PHẢN HỒI DỮ LIỆU (RESPONSES) ---
class SellerSummaryResponse(BaseModel):
    id: int
    Email: str
    account_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ProductDetailResponse(BaseModel):
    product_id: int
    title: str
    price: float
    description: Optional[str] = None
    thumbnails: Optional[str] = None
    sub_category_id: int
    status_id: int
    condition_id: int
    seller_id: int
    buyer_id: Optional[int] = None
    deleted_at: Optional[datetime] = None
    CreatedAt: Optional[datetime] = None

    seller: Optional[SellerSummaryResponse] = None
    images: List[ProductImageResponse] = []
    value: List[ProductAttributeValueResponse] = []

    model_config = ConfigDict(from_attributes=True)

class ProductListItemResponse(BaseModel):
    product_id: int
    title: str
    price: float
    thumbnails: Optional[str] = None
    sub_category_id: int
    status_id: int
    condition_id: int
    seller_id: int
    CreatedAt: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class PaginatedProductsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ProductListItemResponse]


# ==============================================================================
# 5. MY PURCHASES SCHEMAS (SEQ 7 - PHASE 2 EXTENSION)
# ==============================================================================
from src.modules.Interaction.schemas import UserSummaryResponse


class MyPurchaseItemResponse(BaseModel):
    product_id: int
    title: str
    price: float
    thumbnail_url: Optional[str] = None
    condition_name: Optional[str] = None
    seller: UserSummaryResponse
    purchased_at: datetime
    has_reviewed: bool = Field(
        False,
        description="Người mua đã gửi đánh giá cho giao dịch sản phẩm này chưa (Seq 7)"
    )

    model_config = ConfigDict(from_attributes=True)


class PaginatedPurchasesResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[MyPurchaseItemResponse]

    model_config = ConfigDict(from_attributes=True)
