from contextlib import asynccontextmanager
import os
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from src.Core.database import SessionLocal
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

# 4. Health Check Endpoints cho AWS Load Balancer (ALB) & Docker HEALTHCHECK
@app.get("/health", tags=["Health Check"], summary="Load Balancer & Container Health Check")
@app.get("/healthz", include_in_schema=False)
def health_check(response: Response, deep: bool = False):
    """
    Endpoint phục vụ AWS ALB Target Group & Docker HEALTHCHECK:
    - Mặc định (Liveness): Đảm bảo tiến trình FastAPI còn phản hồi tốt (HTTP 200).
    - Deep Check (?deep=true): Kiểm tra kết nối Database (trả HTTP 503 nếu mất kết nối DB).
    """
    db_status = "disconnected"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    if deep and db_status != "connected":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "service": "unimarket-api",
            "database": db_status
        }

    return {
        "status": "healthy",
        "service": "unimarket-api",
        "database": db_status
    }


@app.get("/health/ready", tags=["Health Check"], summary="Database Readiness Check")
def readiness_check(response: Response):
    """Kiểm tra chuyên sâu (Readiness) kết nối DB trước khi ALB cấp traffic."""
    return health_check(response=response, deep=True)


# 5. Đăng ký các Router API
app.include_router(auth_controller.router)
app.include_router(user_controller.router)
app.include_router(masterdata_controller.router)
app.include_router(product_controller.router)
app.include_router(interaction_controller.router)
app.include_router(admin_controller.router)
app.include_router(appeal_controller.router)
app.include_router(upload_router)
