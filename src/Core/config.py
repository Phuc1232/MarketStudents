from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# --- MAIL / SMTP CONFIGURATION (Gmail Local -> AWS SES Production) ---
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_FROM = os.getenv("MAIL_FROM", os.getenv("MAIL_USERNAME", "noreply@unimarket.vn"))
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "UniMarket")

# --- REDIS CONFIGURATION (Production / Optional Local) ---
# Format: redis://:password@host:port/db (Leave empty to use in-memory RAM fallback)
REDIS_URL = os.getenv("REDIS_URL", "").strip() or None
