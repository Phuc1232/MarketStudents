from pydantic import BaseModel, ConfigDict
from typing import Optional, List

class WardResponse(BaseModel):
    ward_id: int
    ward_name: str
    ward_type: Optional[str] = None
    district_id: int

    model_config = ConfigDict(from_attributes=True)

class DistrictResponse(BaseModel):
    district_id: int
    district_name: Optional[str] = None
    district_type: Optional[str] = None
    province_id: int

    model_config = ConfigDict(from_attributes=True)

class ProvinceResponse(BaseModel):
    province_id: int
    province_name: str
    province_type: Optional[str] = None
    code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- Category & Dynamic EAV Schemas ---
class AttributeOptionResponse(BaseModel):
    option_id: int
    option_value: str

    model_config = ConfigDict(from_attributes=True)

class AttributeResponse(BaseModel):
    attribute_id: int
    name: Optional[str] = None
    data_type: Optional[str] = None
    option: List[AttributeOptionResponse] = []

    model_config = ConfigDict(from_attributes=True)

class SubCategoryResponse(BaseModel):
    sub_category_id: int
    category_id: int
    name: str

    model_config = ConfigDict(from_attributes=True)

class CategoryTreeResponse(BaseModel):
    category_id: int
    name: str
    slug: Optional[str] = None
    icon_url: Optional[str] = None
    subcategories: List[SubCategoryResponse] = []

    model_config = ConfigDict(from_attributes=True)