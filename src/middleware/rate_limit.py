"""
Rate Limiting Middleware cho UniMarket API.
- Bảo vệ hệ thống khỏi tấn công từ chối dịch vụ (DDoS), Brute-force mật khẩu và spam OTP.
- Hỗ trợ kiến trúc Dual-Backend:
    + Sử dụng Redis (khi cấu hình REDIS_URL trong file .env) cho môi trường Multi-worker / Production.
    + Tự động Fallback sang In-Memory (RAM) khi chạy Local Development hoặc khi Redis mất kết nối.
- Nhận diện chính xác IP của Client qua Reverse Proxy (Nginx, Traefik, Cloudflare) nhờ X-Forwarded-For / X-Real-IP.
- Miễn trừ cho các kết nối WebSocket (/ws/*), tài liệu Swagger/OpenAPI (/docs, /redoc, /openapi.json) và CORS preflight (OPTIONS).
"""

import time
import logging
from typing import Dict, Tuple, Optional
from collections import defaultdict
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from src.Core.config import REDIS_URL

logger = logging.getLogger("unimarket.rate_limit")


class InMemoryRateLimitBackend:
    """
    Bộ đếm lưu lượng trong RAM sử dụng thuật toán Sliding Window Counter.
    Hoàn toàn thread-safe, phục vụ môi trường Local Development mà không phụ thuộc Redis.
    """
    def __init__(self):
        self._history: Dict[str, list] = defaultdict(list)
        self._lock = Lock()
        self._last_cleanup = time.time()

    def _cleanup_stale_keys(self, now: float):
        """Dọn dẹp các key đã hết hạn để giải phóng bộ nhớ RAM định kỳ mỗi 5 phút."""
        if now - self._last_cleanup < 300:
            return
        self._last_cleanup = now
        stale_keys = [k for k, v in self._history.items() if not v or (now - v[-1] > 3600)]
        for k in stale_keys:
            self._history.pop(k, None)

    def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int, int]:
        """
        Kiểm tra trạng thái rate limit của key.
        Trả về Tuple: (is_limited: bool, remaining: int, retry_after: int)
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            self._cleanup_stale_keys(now)

            # 1. Loại bỏ các request đã nằm ngoài cửa sổ trượt (Sliding Window)
            timestamps = [ts for ts in self._history[key] if ts > window_start]
            self._history[key] = timestamps

            count = len(timestamps)
            remaining = max(0, max_requests - count)

            # 2. Nếu đã chạm hoặc vượt quá ngưỡng cho phép
            if count >= max_requests:
                earliest = timestamps[0]
                retry_after = max(1, int(window_seconds - (now - earliest)))
                return True, 0, retry_after

            # 3. Ghi nhận request hợp lệ mới
            self._history[key].append(now)
            return False, remaining - 1, 0


class RedisRateLimitBackend:
    """
    Bộ đếm lưu lượng phân tán trên Redis sử dụng Sorted Set (ZSET).
    Đảm bảo tính nhất quán trên môi trường Production chạy nhiều Uvicorn Workers / Docker Containers.
    """
    def __init__(self, redis_url: str):
        import redis
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        # Kiểm tra kết nối sẵn sàng
        self.client.ping()

    def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int, int]:
        now = time.time()
        window_start = now - window_seconds
        redis_key = f"ratelimit:{key}"

        pipe = self.client.pipeline()
        # Loại bỏ các request cũ hơn window_start
        pipe.zremrangebyscore(redis_key, 0, window_start)
        # Đếm số lượng request trong window hiện tại
        pipe.zcard(redis_key)
        # Lấy timestamp của request sớm nhất trong window để tính thời gian chờ retry_after
        pipe.zrange(redis_key, 0, 0, withscores=True)
        results = pipe.execute()

        current_count = results[1]
        earliest_items = results[2]

        if current_count >= max_requests:
            if earliest_items:
                earliest_time = earliest_items[0][1]
                retry_after = max(1, int(window_seconds - (now - earliest_time)))
            else:
                retry_after = window_seconds
            return True, 0, retry_after

        # Ghi nhận request hiện tại vào Sorted Set và đặt TTL tự hủy
        pipe = self.client.pipeline()
        pipe.zadd(redis_key, {str(now): now})
        pipe.expire(redis_key, window_seconds + 5)
        pipe.execute()

        remaining = max_requests - (current_count + 1)
        return False, remaining, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware kiểm soát tần suất truy cập API toàn cục và theo từng route nhạy cảm.
    """
    # Cấu hình giới hạn: (max_requests, window_seconds)
    ROUTE_LIMITS = {
        "/auth/login": (5, 60),                       # Tối đa 5 lần login / 1 phút (chống Brute-force)
        "/auth/register": (5, 60),                    # Tối đa 5 lần đăng ký / 1 phút (chống clone tài khoản)
        "/auth/forgot-password/request-otp": (3, 60), # Tối đa 3 lần gửi OTP / 1 phút (chống spam mail)
        "/auth/forgot-password/verify-otp": (10, 60), # Tối đa 10 lần nhập thử OTP / 1 phút (chống đoán OTP)
    }
    DEFAULT_GLOBAL_LIMIT = (100, 60)                  # Mặc định: 100 requests / 1 phút cho các endpoint khác

    EXEMPT_PATHS = {
        "/health",
        "/healthz",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico"
    }

    def __init__(self, app):
        super().__init__(app)
        self.in_memory = InMemoryRateLimitBackend()
        self.redis_backend: Optional[RedisRateLimitBackend] = None
        self._init_backend()

    def _init_backend(self):
        if REDIS_URL:
            try:
                self.redis_backend = RedisRateLimitBackend(REDIS_URL)
                logger.info("[RateLimit] Khởi tạo kết nối Redis thành công cho Rate Limiter.")
            except Exception as e:
                logger.warning(f"[RateLimit] Kết nối Redis thất bại ({e}). Tự động fallback sang In-Memory.")
                self.redis_backend = None
        else:
            logger.info("[RateLimit] Không tìm thấy REDIS_URL trong .env. Sử dụng In-Memory Rate Limiter.")

    def _get_client_ip(self, request: Request) -> str:
        # Nhận diện IP thực của client khi đứng sau Reverse Proxy (Nginx, Traefik, Cloudflare, AWS ALB)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        return request.client.host if request.client else "127.0.0.1"

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Bỏ qua các giao thức không phải HTTP (như kết nối WebSocket /ws/*)
        if request.scope.get("type") != "http":
            return await call_next(request)

        # 2. Không giới hạn các yêu cầu CORS preflight (OPTIONS) để tránh chặn nhầm frontend
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # 3. Bỏ qua các tài liệu API docs và static files
        if path in self.EXEMPT_PATHS or path.startswith("/static"):
            return await call_next(request)

        client_ip = self._get_client_ip(request)

        # 4. Xác định hạn ngạch theo endpoint hoặc áp dụng hạn ngạch chung
        max_requests, window_seconds = self.ROUTE_LIMITS.get(path, self.DEFAULT_GLOBAL_LIMIT)
        rate_key = f"{client_ip}:{path}"

        is_limited = False
        remaining = 0
        retry_after = 0

        # 5. Kiểm tra lưu lượng với cơ chế dự phòng an toàn (Fail-safe)
        try:
            if self.redis_backend:
                is_limited, remaining, retry_after = self.redis_backend.is_rate_limited(
                    rate_key, max_requests, window_seconds
                )
            else:
                is_limited, remaining, retry_after = self.in_memory.is_rate_limited(
                    rate_key, max_requests, window_seconds
                )
        except Exception as e:
            logger.error(f"[RateLimit] Lỗi backend Redis ({e}), tự động chuyển sang In-Memory.")
            self.redis_backend = None
            is_limited, remaining, retry_after = self.in_memory.is_rate_limited(
                rate_key, max_requests, window_seconds
            )

        # 6. Nếu vượt quá hạn ngạch -> Trả về HTTP 429 Too Many Requests
        if is_limited:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Bạn đã gửi quá nhiều yêu cầu trong thời gian ngắn. Vui lòng thử lại sau.",
                    "retry_after_seconds": retry_after
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0"
                }
            )

        # 7. Cho phép request tiếp tục đi vào router và gắn thêm headers thông tin vào phản hồi
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

