from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from src.middleware import RateLimitMiddleware
from src.modules.auth import auth_controller
from src.modules.User import user_controller
from src.modules.Masterdata import masterdata_controller
from src.modules.Product import product_controller
from src.modules.Interaction import interaction_controller
from src.modules.Admin import admin_controller, appeal_controller
from src.modules.Upload import upload_router
from src.cron_jobs.scheduler import start_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi động Cron Jobs Scheduler chạy ngầm cùng ứng dụng
    start_scheduler()
    yield
    # Tắt an toàn Scheduler khi dừng server
    shutdown_scheduler()


app = FastAPI(
    title="UniMarket API",
    version="1.0.0",
    lifespan=lifespan
)

# 1. Đăng ký Rate Limit Middleware (Chống DDoS, Brute-force & Spam OTP)
app.add_middleware(RateLimitMiddleware)

# 2. Đăng ký CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Mount thư mục tĩnh phục vụ file upload ở môi trường local development
os.makedirs(os.path.join("static", "uploads"), exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 4. Đăng ký các Router API
app.include_router(auth_controller.router)
app.include_router(user_controller.router)
app.include_router(masterdata_controller.router)
app.include_router(product_controller.router)
app.include_router(interaction_controller.router)
app.include_router(admin_controller.router)
app.include_router(appeal_controller.router)
app.include_router(upload_router)
