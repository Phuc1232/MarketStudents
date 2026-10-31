from pydantic import BaseModel, EmailStr, Field, model_validator
from datetime import datetime
from typing import Optional

class Register(BaseModel):
    """
    Email: EmailStr
    PassWord: str
    account_type: str
    """
    Email: EmailStr
    PassWord: str
    account_type: str

class Register_response(BaseModel):
    Email: EmailStr
    isActive: bool
    CreatedAt: datetime
    account_type: str


class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: int

class GoogleAuthenRequest(BaseModel):
    id_token: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None


# ==============================================================================
# SCHEMAS CHO LUỒNG QUÊN MẬT KHẨU (FORGOT / RESET PASSWORD - 3 STEPS)
# ==============================================================================

class ForgotPasswordRequest(BaseModel):
    """Bước 1: Tiếp nhận email yêu cầu đặt lại mật khẩu"""
    email: EmailStr = Field(
        ...,
        description="Địa chỉ email đã đăng ký tài khoản trên sàn UniMarket"
    )


class VerifyResetOtpRequest(BaseModel):
    """Bước 2: Người dùng nhập mã OTP 6 số để xác thực"""
    email: EmailStr = Field(..., description="Email đã nhận mã OTP")
    otp_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="Mã OTP gồm đúng 6 chữ số"
    )


class VerifyResetOtpResponse(BaseModel):
    """Phản hồi sau khi xác thực OTP thành công: Cấp Reset Token"""
    message: str = "Xác thực OTP thành công. Vui lòng thiết lập mật khẩu mới trong vòng 10 phút."
    reset_token: str = Field(..., description="Token tạm thời có hạn 10 phút dùng để đổi mật khẩu")
    token_type: str = "bearer"


class ResetPasswordRequest(BaseModel):
    """Bước 3: Người dùng gửi token cùng mật khẩu mới để cập nhật"""
    reset_token: str = Field(..., description="Token được cấp ở Bước 2")
    new_password: str = Field(
        ...,
        min_length=6,
        max_length=100,
        description="Mật khẩu mới (tối thiểu 6 ký tự)"
    )
    confirm_password: str = Field(
        ...,
        min_length=6,
        max_length=100,
        description="Xác nhận lại mật khẩu mới"
    )

    @model_validator(mode="after")
    def check_passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Mật khẩu xác nhận không khớp với mật khẩu mới!")
        return self


class ForgotPasswordGeneralResponse(BaseModel):
    """Phản hồi thông điệp chung cho các bước quên mật khẩu"""
    message: str
    email: Optional[str] = None
