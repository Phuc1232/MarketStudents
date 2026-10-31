import random
import jwt
from datetime import timedelta
from typing import Optional
from fastapi import HTTPException, Depends, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select
from google.oauth2 import id_token
from google.auth.transport import requests

from ...api.deps import get_db
from ...Core.config import GOOGLE_CLIENT_ID, ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM
from ...Core.security import get_password_hashed
from ...share.uilts import create_access_token
from src.modules import GoogleAuthenRequest, User_Providers, User, Token, Blacklist, userProfile
from src.modules.Interaction.services import get_user_display_name
from src.share.otp_storage import otp_storage
from src.share.email_service import send_password_reset_otp_email
from src.modules import (
    ForgotPasswordRequest,
    VerifyResetOtpRequest,
    VerifyResetOtpResponse,
    ResetPasswordRequest,
    ForgotPasswordGeneralResponse
)

RESET_TOKEN_EXPIRE_MINUTES = 10


def verify_login_google(data: GoogleAuthenRequest, db: Session = Depends(get_db)):
    try: 
        info_user = id_token.verify_oauth2_token(data.id_token, requests.Request(), GOOGLE_CLIENT_ID)
        user_email = info_user.get("email")
        google_subject_id = info_user.get("sub")
        full_name = info_user.get("name", "")
        avatar_picture = info_user.get("picture", "")

        # 1. Kiểm tra Email có nằm trong Blacklist (Seq 1)
        stmt_black = select(Blacklist).where(Blacklist.blocked_value == user_email.strip().lower())
        if db.scalars(stmt_black).first():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản Google này đã bị chặn khỏi hệ thống UniMarket!"
            )
        
        stmt = select(User_Providers).where(User_Providers.provider_id == google_subject_id, User_Providers.provider_name == "google")
        user_providers = db.scalars(stmt).first()
        if not user_providers:
            user = db.scalars(select(User).where(User.Email == user_email)).first()
            if not user:
                # Tạo bản ghi User mới
                new_user = User(Email=user_email)
                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                user = new_user

                # Đồng bộ thông tin Họ tên & Avatar từ Google vào userProfile (Seq 1)
                name_parts = full_name.split() if full_name else []
                first_name = name_parts[-1] if name_parts else ""
                last_name = " ".join(name_parts[:-1]) if len(name_parts) > 1 else ""

                profile = userProfile(
                    user_id=user.id,
                    first_name=first_name,
                    last_name=last_name,
                    avatar_url=avatar_picture,
                    type_mode="light"
                )
                db.add(profile)
                db.commit()

            new_provider = User_Providers(
                user_id=user.id,
                provider_name="google",
                provider_id=google_subject_id,
                access_token=data.access_token,
                refresh_token=data.refresh_token
            )
            db.add(new_provider)
            db.commit()
        else:
            user = db.scalars(select(User).where(User.id == user_providers.user_id)).first()
            
        if not user.isActive:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản Google của bạn đã bị khóa. Vui lòng liên hệ quản trị viên hoặc gửi yêu cầu mở khóa!"
            )

        access_token_expire = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
        access_token = create_access_token({"user_id": user.id}, access_token_expire)
        
        return Token(access_token=access_token, token_type="bearer")
    except ValueError:
        raise HTTPException(status_code=401, detail="Token Google không hợp lệ hoặc đã hết hạn")


# ==============================================================================
# LOGIC NGHIỆP VỤ CHO LUỒNG QUÊN MẬT KHẨU (FORGOT / RESET PASSWORD - 3 STEPS)
# ==============================================================================

def request_forgot_password(
    form: ForgotPasswordRequest,
    db: Session,
    background_tasks: Optional[BackgroundTasks] = None
) -> ForgotPasswordGeneralResponse:
    """
    Bước 1: Tiếp nhận email yêu cầu quên mật khẩu và phát mã OTP về Email.
    """
    clean_email = form.email.strip().lower()

    # 1. Tìm người dùng theo email
    stmt = select(User).where(User.Email == clean_email)
    user = db.scalars(stmt).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tài khoản nào liên kết với địa chỉ email này trên UniMarket!"
        )

    # 2. Kiểm tra tài khoản có bị khóa không
    if not user.isActive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này hiện đang bị khóa do vi phạm quy chế. Không thể thực hiện đặt lại mật khẩu!"
        )

    # 3. Kiểm tra danh sách đen Blacklist
    stmt_bl = select(Blacklist).where(Blacklist.blocked_value == clean_email)
    if db.scalars(stmt_bl).first():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email này đã bị chặn vĩnh viễn khỏi hệ thống UniMarket!"
        )

    # 4. Kiểm tra Rate-Limit Cooldown 60s
    remaining = otp_storage.get_remaining_cooldown(clean_email, cooldown_seconds=60, purpose="forgot_pwd")
    if remaining > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Thao tác quá nhanh! Vui lòng đợi {remaining} giây trước khi yêu cầu cấp lại mã OTP mới."
        )

    # 5. Sinh mã OTP 6 số
    otp_code = f"{random.randint(100000, 999999)}"

    # 6. Lưu vào Hybrid OTP Storage với thời hạn 5 phút (300 giây)
    otp_storage.save_otp(
        email=clean_email,
        user_id=user.id,
        otp=otp_code,
        ttl_seconds=300,
        purpose="forgot_pwd"
    )

    # In ra console để dev/tester dễ quan sát
    try:
        print("\n" + "=" * 60)
        print(f"[UNIMARKET FORGOT PASSWORD] YÊU CẦU ĐẶT LẠI MẬT KHẨU")
        print(f"-> Gửi tới Email : {clean_email}")
        print(f"-> Mã OTP (6 số) : {otp_code}")
        print(f"-> Hạn sử dụng   : 5 phút")
        print("=" * 60 + "\n")
    except Exception:
        pass

    # 7. Gửi Email HTML qua BackgroundTasks (Non-blocking)
    user_name = get_user_display_name(user)
    if background_tasks:
        background_tasks.add_task(
            send_password_reset_otp_email,
            to_email=clean_email,
            user_name=user_name,
            otp_code=otp_code,
            expire_minutes=5
        )
    else:
        send_password_reset_otp_email(clean_email, user_name, otp_code, 5)

    return ForgotPasswordGeneralResponse(
        message="Mã xác thực OTP đã được gửi đến email của bạn. Vui lòng kiểm tra hộp thư!",
        email=clean_email
    )


def verify_forgot_password_otp(
    form: VerifyResetOtpRequest,
    db: Session
) -> VerifyResetOtpResponse:
    """
    Bước 2: Xác thực mã OTP và cấp vé thông hành Reset Token (JWT 10 phút) bằng create_access_token.
    """
    clean_email = form.email.strip().lower()

    # 1. Kiểm tra tài khoản tồn tại
    user = db.scalars(select(User).where(User.Email == clean_email)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tài khoản không tồn tại!"
        )

    # 2. Xác thực và tự hủy OTP (One-time use)
    is_valid, reason = otp_storage.verify_and_delete_otp(
        email=clean_email,
        otp_code=form.otp_code,
        user_id=user.id,
        purpose="forgot_pwd"
    )

    if not is_valid:
        if reason == "NOT_FOUND_OR_EXPIRED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã OTP đã hết hạn (quá 5 phút) hoặc không tìm thấy yêu cầu. Vui lòng xin cấp lại mã mới!"
            )
        elif reason == "INVALID_OTP":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã OTP không chính xác. Vui lòng kiểm tra lại email!"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Xác thực OTP thất bại. Vui lòng thử lại!"
            )

    # 3. Tạo Reset Token ngắn hạn (Tái sử dụng create_access_token với hạn 10 phút)
    reset_token = create_access_token(
        data={
            "user_id": user.id,
            "email": user.Email,
            "purpose": "password_reset"
        },
        expire_delta=timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    )

    return VerifyResetOtpResponse(
        message="Xác thực OTP thành công. Vui lòng tạo mật khẩu mới trong vòng 10 phút.",
        reset_token=reset_token
    )


def reset_password_with_token(
    form: ResetPasswordRequest,
    db: Session
) -> ForgotPasswordGeneralResponse:
    """
    Bước 3: Tiếp nhận Reset Token hợp lệ và cập nhật mật khẩu mới mã hóa bằng Argon2.
    """
    # 1. Giải mã và kiểm tra tính hợp lệ của reset_token
    try:
        payload = jwt.decode(form.reset_token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phiên làm việc đã hết hạn (quá 10 phút). Vui lòng thực hiện lại từ đầu!"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token đặt lại mật khẩu không hợp lệ hoặc đã bị thay đổi trái phép!"
        )

    # 2. Kiểm tra claim mục đích (Security Guard)
    if payload.get("purpose") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token không có quyền thực hiện thao tác đặt lại mật khẩu!"
        )

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token bị thiếu thông tin định danh người dùng!"
        )

    # 3. Lấy User từ cơ sở dữ liệu
    user = db.get(User, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Người dùng không tồn tại!"
        )

    # 4. Mã hóa mật khẩu mới bằng Argon2
    hashed_new_password = get_password_hashed(form.new_password)
    user.PassWord = hashed_new_password

    db.commit()
    db.refresh(user)

    return ForgotPasswordGeneralResponse(
        message="Đặt lại mật khẩu thành công! Bây giờ bạn có thể đăng nhập bằng mật khẩu mới của mình.",
        email=user.Email
    )
