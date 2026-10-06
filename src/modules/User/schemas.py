from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import Optional
from datetime import datetime
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

class StudentOtpRequest(BaseModel):
    edu_email: EmailStr = Field(
        ..., 
        description="Email trường đại học kết thúc bằng đuôi .edu.vn (vd: sv@ut.edu.vn)"
    )

class StudentOtpConfirm(BaseModel):
    edu_email: EmailStr = Field(..., description="Email trường đã nhận mã OTP")
    otp_code: str = Field(
        ..., 
        min_length=6, 
        max_length=6, 
        description="Mã OTP gồm 6 chữ số"
    )

class StudentCardUpload(BaseModel):
    student_card_img: str = Field(
        ..., 
        description="Link ảnh chụp thẻ sinh viên (luồng dự phòng khi trường không có email)"
    )

class StudentVerificationResponse(BaseModel):
    user_id: int
    edu_email: Optional[str] = None
    student_card_img: Optional[str] = None
    status: str
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)