from pydantic import BaseModel, EmailStr
from datetime import datetime
class Register(BaseModel):
    """
    Email: EmailStr
    PassWord: str
    account_type: str
    """
    
    Email: EmailStr
    PassWord: str
    account_type: str
class Register_response(BaseModel):
    Email: EmailStr
    isActive: bool
    CreatedAt: datetime
    account_type: str


class Token(BaseModel):
    access_token:str
    token_type: str

class TokenData(BaseModel):
    user_id: int

class GoogleAuthenRequest(BaseModel):
    id_token: str
    access_token: str
    refesh_token: str