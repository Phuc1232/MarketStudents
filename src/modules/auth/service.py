from fastapi import HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from ...api.deps import get_db
from ...Core.config import GOOGLE_CLIENT_ID, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta
from ...share.uilts import create_access_token
from src.modules import GoogleAuthenRequest,User_Providers, User, Token
from google.oauth2 import id_token
from google.auth.transport import requests


def verify_login_google(data: GoogleAuthenRequest, db: Session= Depends(get_db)):
    try: 
        info_user= id_token.verify_oauth2_token(data.id_token,requests.Request(), GOOGLE_CLIENT_ID)
        user_email=info_user.get("email")
        google_subject_id=info_user.get("sub")
        
        stmt=select(User_Providers).where(User_Providers.provider_id==google_subject_id, User_Providers.provider_name=="google")
        user_providers=db.scalars(stmt).first()
        if not user_providers:
            user=db.scalars(select(User).where(User.Email==user_email)).first()
            if not user:
                new_user=User(Email=user_email)
                db.add(new_user)
                db.commit()
                db.refresh(new_user)
            new_provider=User_Providers(user_id=user.id ,provider_name="google", provider_id=google_subject_id, access_toke=data.access_token, refesh_token=data.refesh_token)
            db.add(new_provider)
            db.commit()
        else:
            user = db.scalars(select(User).where(User.id == user_providers.user_id)).first()
            
        access_token_expire = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
        access_token = create_access_token({"user_id": user.id}, access_token_expire)
        
        return Token(access_token=access_token, token_type="bearer")
    except ValueError:
        raise HTTPException(status_code=401, detail="Token Google không hợp lệ hoặc đã hết hạn")



            

