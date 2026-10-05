from fastapi import FastAPI, Depends, HTTPException, status, APIRouter
from src.modules import Register, Token, User, Register_response, User_Update, UserProfileUpdate, UserProfileResponse
from sqlalchemy.orm import Session
from ...api.deps import get_db
from typing import Annotated
from .service import get_current_user, get_all_user, get_user, delete_user_for_user, update_pass_user_for_user, get_profile,update_profile 

router=APIRouter(
    prefix="/user",
    tags=["User"],
    dependencies=[Depends(get_current_user)]
)


@router.get("/all", response_model= list[Register_response], status_code=status.HTTP_200_OK)
def get_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_all_user(user.role_id, db)

@router.get("/me", response_model=Register_response, status_code=status.HTTP_200_OK)
def get_me(db: Session=Depends(get_db), user: User =Depends(get_current_user)):
    return get_user(user.id,db)
@router.get("/{id}", response_model=Register_response, status_code=status.HTTP_200_OK)
def get_user_id(id :int, db: Session= Depends(get_db)):
    return get_user(id,db)

@router.delete("/me", status_code=status.HTTP_200_OK)
def del_user(user: User =Depends(get_current_user), db:Session =Depends(get_db)):
    return delete_user_for_user(user.id,db)

@router.put("/password/me", status_code=status.HTTP_200_OK)
def update_pass_user(form_update: User_Update ,user: User=Depends(get_current_user), db: Session= Depends(get_db)):
    return update_pass_user_for_user(form_update,user.id,db)

@router.get("/profile/me", response_model= UserProfileResponse, status_code= status.HTTP_200_OK)
def read_my_profile (user: User = Depends(get_current_user), db: Session= Depends(get_db)):
    return get_profile(user.id, db)

@router.put("/profile/me", response_model= UserProfileResponse, status_code=status.HTTP_200_OK)
def update_my_profile (form: UserProfileUpdate, user: User = Depends(get_current_user) ,db: Session= Depends(get_db)):
    return update_profile(user.id, form,db)