from fastapi import Depends, HTTPException, status
from src.modules import User, TokenData, Token, Register, User_Update, User_Providers, userProfile, UserProfileUpdate
from src.share.uilts import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM, timedelta, jwt
from src.Core.security import get_password_hashed, verify_password
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.api.deps import get_db
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated
#from datetime import timedelta
#from ...Core.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
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
    