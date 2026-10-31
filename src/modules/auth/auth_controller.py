from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Annotated

from ...api.deps import get_db
from src.modules import (
    Register, Register_response, GoogleAuthenRequest,
    ForgotPasswordRequest, VerifyResetOtpRequest, VerifyResetOtpResponse,
    ResetPasswordRequest, ForgotPasswordGeneralResponse
)
from ..User.service import user_register, authenticate_user
from .service import (
    verify_login_google,
    request_forgot_password,
    verify_forgot_password_otp,
    reset_password_with_token
)

router = APIRouter(
   prefix="/auth",
   tags=["Auth"]
)

@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=Register_response)
def register(user: Register, db: Session = Depends(get_db)):
   return user_register(user, db)
   

@router.post("/login", status_code=status.HTTP_200_OK)
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
   return authenticate_user(form_data.username, form_data.password, db)

@router.post("/login/google", status_code=status.HTTP_201_CREATED)
def login_Google(data: GoogleAuthenRequest, db: Session = Depends(get_db)):
   return verify_login_google(data, db)


# ==============================================================================
# LUỒNG QUÊN MẬT KHẨU (FORGOT / RESET PASSWORD - 3 STEPS)
# ==============================================================================

@router.post(
    "/forgot-password/request-otp",
    response_model=ForgotPasswordGeneralResponse,
    status_code=status.HTTP_200_OK,
    summary="Bước 1: Nhập email để nhận mã OTP đặt lại mật khẩu"
)
def forgot_password_request_otp(
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    - Kiểm tra email tồn tại và không bị khóa.
    - Kiểm tra cooldown chống spam 60 giây.
    - Sinh mã OTP 6 số và gửi ngầm qua email.
    """
    return request_forgot_password(form=body, db=db, background_tasks=background_tasks)


@router.post(
    "/forgot-password/verify-otp",
    response_model=VerifyResetOtpResponse,
    status_code=status.HTTP_200_OK,
    summary="Bước 2: Xác thực mã OTP và nhận Reset Token"
)
def forgot_password_verify_otp(
    body: VerifyResetOtpRequest,
    db: Session = Depends(get_db)
):
    """
    - Kiểm tra mã OTP người dùng nhập.
    - Hủy OTP ngay lập tức sau khi xác minh đúng (One-time-use).
    - Cấp `reset_token` có hiệu lực trong 10 phút.
    """
    return verify_forgot_password_otp(form=body, db=db)


@router.post(
    "/forgot-password/reset",
    response_model=ForgotPasswordGeneralResponse,
    status_code=status.HTTP_200_OK,
    summary="Bước 3: Nhập mật khẩu mới kèm Reset Token để hoàn tất"
)
def forgot_password_reset(
    body: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    - Giải mã `reset_token`, kiểm tra tính nguyên vẹn và thời hạn.
    - Mã hóa mật khẩu mới bằng Argon2 và cập nhật vào Database.
    """
    return reset_password_with_token(form=body, db=db)
