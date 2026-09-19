from pydantic import BaseModel


class User_Update(BaseModel):
    current_password: str
    new_password: str