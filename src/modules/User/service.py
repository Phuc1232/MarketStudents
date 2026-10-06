from fastapi import Depends, HTTPException, status
from src.modules import (User, TokenData, Token, Register, User_Update, 
                         User_Providers, userProfile, UserProfileUpdate,
                         Address, AddressCreate,
                         StudentVerification)
from src.share.uilts import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM, timedelta, jwt, datetime, timezone
from src.Core.security import get_password_hashed, verify_password
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.api.deps import get_db
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated
import random
import re
from datetime import timedelta
import jwt
oauth_schemas=OAuth2PasswordBearer(tokenUrl="auth/login")



def user_register(user: Register, db: Session= Depends(get_db)):
    stmt=select(User).where(User.Email==user.Email)
    user_model=db.scalars(stmt).first()
    if user_model:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already exits")
    user.PassWord=get_password_hashed(user.PassWord)
    new_user=User(**user.model_dump())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    new_provider=User_Providers(user_id=new_user.id ,provider_name="local")
    db.add(new_provider)
    db.commit()
    return new_user

def get_all_user(role_id: int, db: Session= Depends(get_db)):
    if(role_id==1):
        stmt=select(User)
        user=db.scalars(stmt).all()
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="ONLY ADMIN!!!")
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not Found")
    return user

def delete_user_for_user(user_id: int, db: Session=Depends(get_db)):
    # stmt=select(User).where(User.id==user_id)
    # user=db.scalars(stmt).first()
    user=db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Loi!!!!")
    db.delete(user)
    db.commit()

def update_pass_user_for_user(from_update: User_Update, user_id: int , db: Session= Depends(get_db)):
    user=db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Loi!!!!")
    user.PassWord=get_password_hashed(from_update.new_password)
    db.commit() 
    db.refresh(user)
    
def get_user(user_id: int, db: Session= Depends(get_db)):
    stmt=select(User).where(User.id==user_id)
    user=db.scalars(stmt).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Khong ton tai!!!")
    return user

def get_current_user(token:  Annotated[str, Depends(oauth_schemas)], db: Session=Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload=jwt.decode(token,SECRET_KEY, algorithms=[ALGORITHM])
        user_id=payload.get("user_id")
        if user_id is None:
            raise credentials_exception
        token_data=TokenData(user_id=user_id)
    except Exception:
        raise credentials_exception
    user=get_user(token_data.user_id, db)
    if not user:
        raise credentials_exception
    return user

def authenticate_user(username: str, password: str ,db: Session= Depends(get_db)):
    dummy_password=get_password_hashed("thienphucne")
    stmt=select(User).where(username==User.Email)
    user=db.scalars(stmt).first()
    if not user:
        verify_password(password,dummy_password)
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sai Tai Khoan Hoac Mat Khau")
    if not verify_password(password, user.PassWord):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sai Tai Khoan Hoac Mat Khau")
    access_token_expire= timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token=create_access_token({"user_id":user.id}, access_token_expire)
    
    return Token(access_token=access_token, token_type="bearer")

def get_profile (user_id: int, db: Session):
    stmt= select(userProfile).where(userProfile.user_id==user_id)
    profile = db.scalars(stmt).first()
    if not profile:
        profile = userProfile(user_id=user_id, type_mode ="Light")
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile
def update_profile (user_id: int, form: UserProfileUpdate , db: Session):
    profile = db.get(userProfile, user_id)
    if not profile:
        profile = userProfile(user_id=user_id, **form.model_dump())
        db.add(profile)
    else:
        for field, value in form.model_dump().items():
            setattr(profile,field,value)
    db.commit()
    db.refresh(profile)
    return profile

def get_user_address (user_id: int, db: Session):
    stmt = select(Address).where(Address.user_id==user_id).order_by(Address.is_default.desc(), Address.address_id.desc())
    return db.scalars(stmt).all()

def add_user_address (user_id: int, form: AddressCreate, db: Session):
    if form.is_default:
        old_address = db.scalars(select(Address).where(Address.user_id==user_id)).all()
        for i in old_address:
            i.is_default=False
    new_address = Address(user_id=user_id, **form.model_dump())
    db.add(new_address)
    db.commit()
    db.refresh(new_address)
    return new_address
def update_address (user_id: int, address_id: int, form: AddressCreate, db: Session):
    stmt = select(Address).where(Address.user_id==user_id,Address.address_id==address_id)
    address= db.scalars(stmt).first()
    if not address:
        raise (
            HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                          detail=f"Khong tim thay address cua {user_id}")
        )
    for field, value in form.model_dump().items():
        setattr(address,field,value)
    db.add(address)
    db.commit()
    db.refresh(address)
    return address

def delete_user_address (address_id: int, user_id: int, db: Session):
    stmt = select(Address).where(Address.address_id == address_id, Address.user_id == user_id)
    addr = db.scalars(stmt).first()
    if not addr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy địa chỉ hoặc bạn không có quyền xóa địa chỉ này"
        )
    db.delete(addr)
    db.commit()
    return {"message": "Đã xóa địa chỉ thành công"}
# In-memory OTP storage: { "edu_email": {"otp": "123456", "user_id": 1, "expires_at": datetime} }
OTP_CACHE ={}
def request_student_otp (user_id: int, edu_email: str, db: Session):
    # check the user's email has "edu"?
    
    email_clean = edu_email.strip().lower()
    if not (email_clean.endswith("edu.vn")):
        raise (
            HTTPException(
                status_code= status.HTTP_401_UNAUTHORIZED, detail=f"Email không hợp lệ! Vui lòng sử dụng email chính thức của trường đại học kết thúc bằng đuôi '.edu.vn'"
            )
        )
    # check the email verifed 
    stmt = select(StudentVerification).where(StudentVerification.edu_email==email_clean,
                                             StudentVerification.status == "Verified")
    exsiting = db.scalars(stmt).first()
    if  exsiting or exsiting.user_id !=user_id:
        raise (
            HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email sinh viên này đã được liên kết hoặc xác minh bởi một tài khoản khác trên UniMarket!"
            )
        )
    otp = f"{random.randint(100000,999999)}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    OTP_CACHE[email_clean]={
        "otp": otp,
        "user_id": user_id,
        "expires_at": expires_at
    }
    #In mã OTP ra Console phục vụ kiểm thử môi trường dev
    print("\n" + "="*60)
    print(f"[UNIMARKET OTP SERVICE] GỬI MÃ XÁC THỰC SINH VIÊN")
    print(f"-> Gửi tới Email: {email_clean}")
    print(f"-> Mã OTP (6 số): {otp}")
    print(f"-> Thời hạn     : 5 phút (hết hạn lúc {expires_at.strftime('%H:%M:%S')})")
    print("="*60 + "\n")

    return {
        "message": "Mã OTP đã được gửi thành công đến email trường của bạn. Vui lòng kiểm tra hộp thư!",
        "edu_email": email_clean
    }

def confirm_student_otp (user_id: int, edu_email: str, otp_code: int, db: Session):
    email_clean = edu_email.strip().lower()
    cache =OTP_CACHE.get(email_clean)
    if not cache or cache["user_id"]!=user_id:
        raise (
            HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy yêu cầu xác thực cho email này hoặc bạn chưa gửi yêu cầu lấy mã OTP!"
            )
        )
    if datetime.now(timezone.utc) > cache ["expires_at"]:
        OTP_CACHE.pop(email_clean,None)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã OTP đã hết hạn (quá 5 phút). Vui lòng yêu cầu cấp mã mới!"
        )
    if cache["otp"] != otp_code.strip():
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã OTP không chính xác. Vui lòng kiểm tra lại!"
        )
    stmt = select (StudentVerification).where(StudentVerification.user_id==user_id)
    verfication = db.scalars(stmt).first()
    if not verfication:
        verfication = StudentVerification(
            user_id=user_id,
            status="Verified",
            edu_email = email_clean
        )
        db.add(verfication)
    else:
        verfication.edu_email=email_clean
        verfication.status="Verified"
        verfication.submitted_at=datetime.now(timezone.utc)
    db.commit()
    db.refresh(verfication)

    user= db.get (User,user_id)
    if user:
        user.account_type="Student"
        user.role_id=3
    OTP_CACHE.pop(email_clean,None)
    return verfication