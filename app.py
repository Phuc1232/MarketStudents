from fastapi import FastAPI
from src.modules.auth import auth_controller
from src.modules.User import user_controller
#Bas e.metadata.create_all(bind=engine)
# khoi tao doi tuong tu class Oauth2PasswordRequestForm


app=FastAPI()

app.include_router(auth_controller.router)
app.include_router(user_controller.router)



