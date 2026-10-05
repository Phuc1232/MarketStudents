from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class User_Update(BaseModel):
    current_password: str
    new_password: str

class UserProfileUpdate (BaseModel):
    first_name: Optional[str] = Field(None, max_length=100, description="Tên")
    last_name: Optional[str] = Field(None, max_length=100, description="Họ và tên đệm")
    phone_number: Optional[str] = Field(None, max_length=20, description="Số điện thoại liên hệ")
    avatar_url: Optional[str] = Field(None, description="Đường dẫn ảnh đại diện")
    bio: Optional[str] = Field(None, description="Giới thiệu ngắn gọn bản thân")
    type_mode: Optional[str] = Field(default="light", description="Cài đặt giao diện: 'light' hoặc 'dark'")

class UserProfileResponse(BaseModel):
    user_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    type_mode: Optional[str] = "light"

    model_config = ConfigDict(from_attributes=True)

class AddressCreate(BaseModel):
    ward_id: int = Field(..., description="ID Phường/Xã từ bảng master_wards")
    specific_name: str = Field(..., max_length=255, description="Địa chỉ cụ thể: Số nhà, tên đường, KTX")
    type: str = Field(default="Nhà riêng", description="Loại địa chỉ: Nhà riêng / Ký túc xá / Công ty")
    is_default: bool = Field(default=True, description="Đặt làm địa chỉ giao dịch mặc định")

class AddressResponse(BaseModel):
    address_id: int
    user_id: int
    ward_id: int
    specific_name: str
    type: str
    is_default: bool

    model_config = ConfigDict(from_attributes=True)

class MessageResponse(BaseModel):
    message: str