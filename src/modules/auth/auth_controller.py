from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from ...api.deps import get_db
from .schemas import Register, Register_response, GoogleAuthenRequest
from typing import Annotated
from ..User.service import user_register, authenticate_user
from .service import verify_login_google

router=APIRouter(
   prefix="/auth",
   tags=["Auth"]
)

@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=Register_response)
def register(user: Register, db: Session= Depends(get_db)):
   return user_register(user, db)
   

@router.post("/login", status_code=status.HTTP_200_OK)
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session= Depends(get_db)):
   return authenticate_user(form_data.username, form_data.password, db)

@router.post("/login/google", status_code=status.HTTP_201_CREATED)
def login_Google(data: GoogleAuthenRequest, db: Session=Depends(get_db)):
   return verify_login_google(data,db)