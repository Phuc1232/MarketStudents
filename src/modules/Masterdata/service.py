from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from src.modules.Masterdata.models import MasterDistrict, MasterProvince, MasterWard
from src.modules.Product.models import Category, SubCategory, Attribute
from fastapi import HTTPException, status

#lay toan bo tinh/tp
def get_all_provinces(db: Session):
  
    stmt= select(MasterProvince).order_by(MasterProvince.province_id)
    return db.scalars(stmt).all()
#lay danh sach quan/huyen theo tinh
def get_districts_by_province(province_id: int, db: Session):
    
    stmt= select (MasterDistrict).where(MasterDistrict.province_id==province_id).order_by(MasterDistrict.district_name)
    return db.scalars(stmt).all()
#lay danh sach phuong/xa theo quan/huyen
def get_wards_by_districts(districts_id: int, db: Session):
    stmt= select(MasterWard).where(MasterWard.district_id==districts_id).order_by(MasterWard.ward_name)
    return db.scalars(stmt).all()

def get_category_tree (db: Session):
    stmt= select(Category).options(selectinload(Category.subcategory))
    categories= db.scalars(stmt).all()
    result =[]
    for cat in categories:
        result.append(
            {
                "category_id": cat.category_id,
                "name": cat.name,
                "slug": cat.slug,
                "icon_url": cat.icon_url,
                "subcategories": cat.subcategory or []
            }
        )
    return result
#lay thuoc tinh dong cho tung subcategory
def get_attributes_by_subcategory (subcategory_id: int, db: Session):
    # kiem tra ton tai sub
    subcat = db.get(SubCategory, subcategory_id)
    if not subcat:
        raise HTTPException(
            status_code= status.HTTP_404_NOT_FOUND,
            detail=f"Danh mục con với ID {subcategory_id} không tồn tại"
        )
    # lien ket toi AttributeOption
    stmt= select(Attribute).where(Attribute.subcategory_id==subcategory_id).options(selectinload(Attribute.option))     
    attributes= db.scalars(stmt).all()
    result=[]
    for att in attributes:
        result.append(
            {
                "attribute_id": att.attribute_id,
                "name": att.name,
                "data_type": att.data_type,
                "option": att.option or []
            }
        )
    return result




