from fastapi import FastAPI, Depends, HTTPException, status, APIRouter
from src.modules import (Register, Token, User, Register_response, 
                         User_Update, UserProfileUpdate, UserProfileResponse,
                         AddressResponse, AddressCreate, 
                         MessageResponse, StudentOtpRequest, StudentOtpConfirm, StudentVerificationResponse, StudentCardUpload,
                         SavedSearchCreate, SavedSearchResponse)
from sqlalchemy.orm import Session
from ...api.deps import get_db
from typing import Annotated
from .service import (get_current_user, get_all_user, get_user, delete_user_for_user, 
update_pass_user_for_user, 
get_profile,update_profile, 
get_user_address, add_user_address, update_address, delete_user_address, 
request_student_otp,confirm_student_otp, upload_student_card, delete_user_by_admin,
get_user_search_history, save_user_search_keyword, delete_user_search_keyword) 

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

@router.get ("/address/me", response_model= list[AddressResponse], status_code=status.HTTP_200_OK)
def read_my_address (user: User= Depends(get_current_user), db: Session =Depends(get_db)):
    return get_user_address(user.id,db)
@router.post("/address/me", response_model=AddressResponse, status_code=status.HTTP_200_OK)
def create_address (form : AddressCreate, user: User =Depends(get_current_user), db: Session =Depends(get_db)):
    return add_user_address(user.id,form,db)

@router.put ("/address/{address_id}/me", response_model=AddressResponse, status_code=status.HTTP_200_OK)
def update_my_address (address_id: int , form: AddressCreate, user: User =Depends(get_current_user), db: Session= Depends(get_db)):
    return update_address (user.id,address_id,form, db)

@router.delete("/addresses/{address_id}", response_model=MessageResponse, status_code=status.HTTP_200_OK)
def remove_address(
    address_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return delete_user_address(address_id, user.id, db)

@router.post("/verify-student/request-otp", status_code=status.HTTP_200_OK)
def create_otp (body: StudentOtpRequest ,user: User= Depends(get_current_user), db: Session= Depends(get_db)):
    return request_student_otp(user.id,body.edu_email,db)

@router.post("/verify-student/confirm-otp", response_model=StudentVerificationResponse, status_code=status.HTTP_200_OK)
def confirm_otp(body: StudentOtpConfirm, user: User= Depends(get_current_user), db: Session= Depends(get_db)):
    return confirm_student_otp(user.id,body.edu_email,body.otp_code,db)

@router.post("/verify-student/upload-card", response_model=StudentVerificationResponse, status_code=status.HTTP_200_OK)
def confirm_student_card(body: StudentCardUpload, user: User= Depends(get_current_user) ,db: Session= Depends(get_db)):
    return upload_student_card(user.id, body.student_card_img,db)


# --- 5. LỊCH SỬ TÌM KIẾM (SAVEDSEARCH - SEQ 14) ---
@router.get("/search-history", response_model=list[SavedSearchResponse], status_code=status.HTTP_200_OK)
def read_search_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Lấy danh sách các từ khóa tìm kiếm gần đây (Seq 14 - Giai đoạn 1)"""
    return get_user_search_history(user.id, db)


@router.post("/search-history", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
def add_search_keyword(form: SavedSearchCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Lưu từ khóa tìm kiếm ngầm của người dùng đã đăng nhập (Seq 14 - Giai đoạn 2 Async)"""
    return save_user_search_keyword(user.id, form.keyword, form.filter_criteria, db)


@router.delete("/search-history/{search_id}", response_model=MessageResponse, status_code=status.HTTP_200_OK)
def remove_search_keyword(search_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Xóa từ khóa khỏi lịch sử tìm kiếm"""
    return delete_user_search_keyword(search_id, user.id, db)


# --- 6. CÁC ENDPOINT THEO ID (ĐẶT Ở CUỐI ĐỂ TRÁNH XUNG ĐỘT ROUTE) ---
@router.get("/{id}", response_model=Register_response, status_code=status.HTTP_200_OK)
def get_user_id(id: int, db: Session = Depends(get_db)):
    return get_user(id, db)


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user_admin(user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return delete_user_by_admin(user_id, user.role_id, db)



