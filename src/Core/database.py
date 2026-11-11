import os
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine

load_dotenv()
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise Exception("Không tìm thấy DATABASE_URL trong file .env")

# -------------------------------------------------------------
# CẤU HÌNH CONNECTION POOLING CHUẨN CLOUD CHO LOAD BALANCER & AWS RDS
# -------------------------------------------------------------
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=DB_POOL_SIZE,          # Số kết nối giữ cố định trong Pool
    max_overflow=DB_MAX_OVERFLOW,    # Số kết nối tối đa được cấp vượt mức khi có spike traffic
    pool_timeout=DB_POOL_TIMEOUT,    # Thời gian tối đa (giây) chờ có kết nối rảnh trước khi báo lỗi
    pool_recycle=DB_POOL_RECYCLE,    # Tự động làm mới kết nối sau 30 phút để tránh bị AWS firewall ngắt ngầm
    pool_pre_ping=True,              # Tự kiểm tra kết nối còn sống trước khi cấp (chống lỗi kết nối chết ngầm)
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()







