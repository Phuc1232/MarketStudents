from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from src.api.deps import get_db
from src.modules import ProvinceResponse, DistrictResponse, WardResponse,AttributeResponse,CategoryTreeResponse
from .service import  get_all_provinces, get_districts_by_province, get_wards_by_districts, get_category_tree, get_attributes_by_subcategory


router = APIRouter(
    prefix="/masterdata",
    tags=["MasterData"]
)

@router.get("/provinces", response_model=List[ProvinceResponse], status_code=status.HTTP_200_OK)
def list_provinces(db: Session =Depends(get_db)):
    return get_all_provinces(db)

@router.get("/provinces/{province_id}/districts", response_model=List[DistrictResponse], status_code=status.HTTP_200_OK)
def list_districts_by_provinces(province_id: int, db: Session = Depends(get_db)):
    return get_districts_by_province(province_id, db)

@router.get("/districts/{district_id}/ward", response_model=List[WardResponse], status_code=status.HTTP_200_OK)
def list_ward_by_dictricts(district_id: int , db: Session= Depends(get_db)):
    return get_wards_by_districts(district_id,db)

@router.get("/category/sub", response_model=List[CategoryTreeResponse], status_code= status.HTTP_200_OK)
def get_sub_by_cat (db: Session = Depends(get_db)):
    return get_category_tree(db)

@router.get ("/subcategory/{subcategory_id}/attribute", response_model= List[AttributeResponse], status_code=status.HTTP_200_OK)
def get_att_by_sub (subcategory_id: int, db: Session =Depends(get_db)):
    return get_attributes_by_subcategory (subcategory_id, db)