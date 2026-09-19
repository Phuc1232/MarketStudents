import jwt
from datetime import datetime, timedelta, timezone
from ..Core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

# Tao Token voi thoi gian het han
def create_access_token(data: dict, expire_delta: timedelta | None =None):
    to_encode=data.copy()
    if expire_delta:
        expire= datetime.now(timezone.utc)+ expire_delta
    else:
        expire=datetime.now(timezone.utc)+ timedelta(minutes=30)
    to_encode.update({"exp":expire})
    encoded_jwt=jwt.encode(to_encode,SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


    
