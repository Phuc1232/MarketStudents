from fastapi import Depends, HTTPException, status
from src.modules import (User, TokenData, Token, Register, User_Update, 
                         User_Providers, userProfile, UserProfileUpdate,
                         Address, AddressCreate,
                         StudentVerification, Blacklist, SavedSearch)
from src.share.uilts import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM, timedelta, jwt, datetime, timezone
from src.Core.security import get_password_hashed, verify_password
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from src.api.deps import get_db
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated, Optional, List
import random
import re
from datetime import timedelta
import jwt
oauth_schemas=OAuth2PasswordBearer(tokenUrl="auth/login")
oauth_schemas_optional=OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def check_email_blacklisted(email: str, db: Session):
    """Kiểm tra email có nằm trong danh sách đen hay không (Seq 1)"""
    stmt = select(Blacklist).where(Blacklist.blocked_value == email.strip().lower())
    blacklisted = db.scalars(stmt).first()
    if blacklisted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Email này đã bị chặn: {blacklisted.reason or 'Vi phạm quy định của hệ thống UniMarket'}"
        )


def user_register(user: Register, db: Session= Depends(get_db)):
    # 1. Kiểm tra Blacklist theo Seq 1
    check_email_blacklisted(user.Email, db)

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
    new_profile = userProfile(user_id=new_user.id, type_mode="light")
    db.add(new_profile)
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

def delete_user_for_user(user_id: int, db: Session):
    # stmt=select(User).where(User.id==user_id)
    # user=db.scalars(stmt).first()
    user=db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Loi!!!!")
    user.isActive = False
    db.commit()
def delete_user_by_admin (user_id: int, role_id: int, db: Session):
    if (role_id ==1 ):
        user=db.get(User,user_id)
        if not user: 
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="NOT FOUND!!!")
        user.isActive = False
        db.commit()
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ONLY ADMIN!!!")
    return {"message": "Vo Hieu Tai Khoan Thanh Cong!!!!"}

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

def get_optional_user(token: Annotated[Optional[str], Depends(oauth_schemas_optional)] = None, db: Session = Depends(get_db)) -> Optional[User]:
    """Dependency trích xuất User nếu có token hợp lệ, trả về None nếu không đăng nhập (Public endpoints)."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            return None
        return get_user(user_id, db)
    except Exception:
        return None

def authenticate_user(username: str, password: str ,db: Session= Depends(get_db)):
    dummy_password=get_password_hashed("thienphucne")
    stmt=select(User).where(User.Email == username)
    user=db.scalars(stmt).first()
    if not user:
        verify_password(password,dummy_password)
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sai Tai Khoan Hoac Mat Khau")
    
    # Kiểm tra tài khoản bị vô hiệu hóa / khóa
    if not user.isActive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn đã bị khóa. Vui lòng liên hệ quản trị viên hoặc gửi yêu cầu kháng cáo mở khóa!"
        )

    # Kiểm tra Blacklist theo Seq 1
    check_email_blacklisted(user.Email, db)

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
    if  exsiting and exsiting.user_id != user_id:
        raise (
            HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email sinh viên này đã được liên kết và xác minh bởi một tài khoản khác trên UniMarket!"
            )
        )
    otp = f"{random.randint(100000,999999)}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    OTP_CACHE[email_clean]={
        "otp": otp,
        "user_id": user_id,
        "expires_at": expires_at
    }
    # In mã OTP ra Console phục vụ kiểm thử môi trường dev
    try:
        print("\n" + "="*60)
        print(f"[UNIMARKET OTP SERVICE] GUI MA XAC THUC SINH VIEN")
        print(f"-> Gui toi Email: {email_clean}")
        print(f"-> Ma OTP (6 so): {otp}")
        print(f"-> Thoi han     : 5 phut (het han luc {expires_at.strftime('%H:%M:%S')})")
        print("="*60 + "\n")
    except Exception:
        pass

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
        user.account_type="Sinh Vien"
        user.role_id=3
    db.commit()
    OTP_CACHE.pop(email_clean,None)
    return verfication

def upload_student_card (user_id: int, card_image_url: str, db: Session):
    stmt = select(StudentVerification).where (StudentVerification.user_id==user_id)
    verfication = db.scalars(stmt).first()
    if not verfication:
        verfication= StudentVerification(
            user_id=user_id,
            status="Pending",
            student_card_img = card_image_url
        )
        db.add(verfication)
    else:
        verfication.student_card_img = card_image_url
        verfication.status = "Pending"
        verfication.submitted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(verfication)
    return verfication


# ==============================================================================
# LỊCH SỬ TÌM KIẾM (SAVEDSEARCH - SEQ 14)
# ==============================================================================

def get_user_search_history(user_id: int, db: Session):
    """Lấy danh sách các từ khóa tìm kiếm gần đây của người dùng (Seq 14)"""
    stmt = select(SavedSearch).where(SavedSearch.user_id == user_id).order_by(SavedSearch.search_id.desc()).limit(10)
    return db.scalars(stmt).all()


def save_user_search_keyword(user_id: int, keyword: str, filter_criteria: Optional[dict], db: Session):
    """Lưu hoặc cập nhật từ khóa tìm kiếm của người dùng (Seq 14)"""
    kw = keyword.strip()
    if not kw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Từ khóa không được để trống")

    stmt = select(SavedSearch).where(
        SavedSearch.user_id == user_id,
        func.lower(SavedSearch.keyword) == kw.lower()
    )
    existing = db.scalars(stmt).first()
    if existing:
        existing.filter_criteria = filter_criteria
        db.commit()
        db.refresh(existing)
        return existing

    new_saved = SavedSearch(
        user_id=user_id,
        keyword=kw,
        filter_criteria=filter_criteria
    )
    db.add(new_saved)
    db.commit()
    db.refresh(new_saved)
    return new_saved


def delete_user_search_keyword(search_id: int, user_id: int, db: Session):
    """Xóa một từ khóa khỏi lịch sử tìm kiếm (Seq 14)"""
    stmt = select(SavedSearch).where(SavedSearch.search_id == search_id, SavedSearch.user_id == user_id)
    item = db.scalars(stmt).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy mục lịch sử tìm kiếm")
    db.delete(item)
    db.commit()
    return {"message": "Đã xóa từ khóa khỏi lịch sử tìm kiếm thành công"}