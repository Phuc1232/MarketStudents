from fastapi import HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from ...api.deps import get_db
from ...Core.config import GOOGLE_CLIENT_ID, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta
from ...share.uilts import create_access_token
from src.modules import GoogleAuthenRequest, User_Providers, User, Token, Blacklist, userProfile
from google.oauth2 import id_token
from google.auth.transport import requests


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




            

