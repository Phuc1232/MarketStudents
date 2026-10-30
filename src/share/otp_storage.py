import json
import logging
import math
import threading
import time
from typing import Optional, Tuple
from src.Core.config import REDIS_URL

logger = logging.getLogger("unimarket.otp_storage")

class BaseOTPStorage:
    def save_otp(self, email: str, user_id: int, otp: str, ttl_seconds: int = 300) -> bool:
        raise NotImplementedError

    def get_otp(self, email: str) -> Optional[dict]:
        raise NotImplementedError

    def get_remaining_cooldown(self, email: str, cooldown_seconds: int = 60) -> int:
        """
        Returns the remaining seconds of cooldown before another OTP can be requested.
        Returns 0 if no cooldown applies (allowed to send).
        """
        raise NotImplementedError

    def verify_and_delete_otp(self, email: str, otp_code: str, user_id: int) -> Tuple[bool, str]:
        """
        Verify the OTP code for an email and user_id.
        Returns:
            (True, "SUCCESS") if valid and deleted.
            (False, "NOT_FOUND_OR_EXPIRED") if not found or TTL expired.
            (False, "USER_MISMATCH") if belongs to another user.
            (False, "INVALID_OTP") if code does not match.
        """
        raise NotImplementedError

    def delete_otp(self, email: str) -> bool:
        raise NotImplementedError


class InMemoryOTPStorage(BaseOTPStorage):
    """
    Thread-safe in-memory OTP cache with timestamp-based TTL expiration.
    Used for local development without Redis dependency.
    """
    def __init__(self):
        self._cache: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _clean_expired(self):
        now = time.time()
        expired_keys = [k for k, v in self._cache.items() if now > v.get("expires_at", 0)]
        for k in expired_keys:
            self._cache.pop(k, None)

    def save_otp(self, email: str, user_id: int, otp: str, ttl_seconds: int = 300) -> bool:
        clean_email = email.strip().lower()
        now = time.time()
        expires_at = now + ttl_seconds
        with self._lock:
            self._clean_expired()
            self._cache[clean_email] = {
                "otp": str(otp).strip(),
                "user_id": int(user_id),
                "created_at": now,
                "expires_at": expires_at
            }
        return True

    def get_otp(self, email: str) -> Optional[dict]:
        clean_email = email.strip().lower()
        with self._lock:
            data = self._cache.get(clean_email)
            if not data:
                return None
            if time.time() > data.get("expires_at", 0):
                self._cache.pop(clean_email, None)
                return None
            return {
                "otp": data["otp"],
                "user_id": data["user_id"],
                "created_at": data.get("created_at", 0),
                "expires_at": data["expires_at"]
            }

    def get_remaining_cooldown(self, email: str, cooldown_seconds: int = 60) -> int:
        clean_email = email.strip().lower()
        with self._lock:
            data = self._cache.get(clean_email)
            if not data:
                return 0
            if time.time() > data.get("expires_at", 0):
                self._cache.pop(clean_email, None)
                return 0
            elapsed = time.time() - data.get("created_at", 0)
            if elapsed < cooldown_seconds:
                return max(1, int(math.ceil(cooldown_seconds - elapsed)))
            return 0

    def verify_and_delete_otp(self, email: str, otp_code: str, user_id: int) -> Tuple[bool, str]:
        clean_email = email.strip().lower()
        clean_code = str(otp_code).strip()
        with self._lock:
            data = self._cache.get(clean_email)
            if not data:
                return False, "NOT_FOUND_OR_EXPIRED"

            if time.time() > data.get("expires_at", 0):
                self._cache.pop(clean_email, None)
                return False, "NOT_FOUND_OR_EXPIRED"

            if data.get("user_id") != int(user_id):
                return False, "USER_MISMATCH"

            if data.get("otp") != clean_code:
                return False, "INVALID_OTP"

            # OTP is valid -> delete immediately (one-time use)
            self._cache.pop(clean_email, None)
            return True, "SUCCESS"

    def delete_otp(self, email: str) -> bool:
        clean_email = email.strip().lower()
        with self._lock:
            return self._cache.pop(clean_email, None) is not None


class RedisOTPStorage(BaseOTPStorage):
    """
    Production-ready Redis OTP storage using Redis Key-Value with native SETEX TTL.
    Eliminates database table writes and auto-evicts expired OTPs.
    """
    def __init__(self, redis_url: str):
        import redis
        self.redis_url = redis_url
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        # Test connection
        self.client.ping()

    def _get_key(self, email: str) -> str:
        return f"otp:student:{email.strip().lower()}"

    def save_otp(self, email: str, user_id: int, otp: str, ttl_seconds: int = 300) -> bool:
        key = self._get_key(email)
        payload = json.dumps({
            "otp": str(otp).strip(),
            "user_id": int(user_id),
            "created_at": time.time()
        })
        # Redis SETEX: sets key with expiration in seconds
        self.client.setex(key, ttl_seconds, payload)
        return True

    def get_otp(self, email: str) -> Optional[dict]:
        key = self._get_key(email)
        raw_val = self.client.get(key)
        if not raw_val:
            return None
        try:
            return json.loads(raw_val)
        except Exception:
            return None

    def get_remaining_cooldown(self, email: str, cooldown_seconds: int = 60) -> int:
        key = self._get_key(email)
        raw_val = self.client.get(key)
        if not raw_val:
            return 0
        try:
            data = json.loads(raw_val)
            elapsed = time.time() - data.get("created_at", 0)
            if elapsed < cooldown_seconds:
                return max(1, int(math.ceil(cooldown_seconds - elapsed)))
            return 0
        except Exception:
            return 0

    def verify_and_delete_otp(self, email: str, otp_code: str, user_id: int) -> Tuple[bool, str]:
        key = self._get_key(email)
        clean_code = str(otp_code).strip()
        raw_val = self.client.get(key)
        if not raw_val:
            return False, "NOT_FOUND_OR_EXPIRED"

        try:
            data = json.loads(raw_val)
        except Exception:
            self.client.delete(key)
            return False, "NOT_FOUND_OR_EXPIRED"

        if data.get("user_id") != int(user_id):
            return False, "USER_MISMATCH"

        if data.get("otp") != clean_code:
            return False, "INVALID_OTP"

        # Valid OTP: delete key immediately
        self.client.delete(key)
        return True, "SUCCESS"

    def delete_otp(self, email: str) -> bool:
        key = self._get_key(email)
        return bool(self.client.delete(key))


class HybridOTPStorage(BaseOTPStorage):
    """
    Smart Adapter:
    - If REDIS_URL is configured and reachable, delegates to RedisOTPStorage.
    - Otherwise, automatically falls back to InMemoryOTPStorage so local development
      is never blocked by missing Redis server.
    """
    def __init__(self):
        self._in_memory = InMemoryOTPStorage()
        self._redis: Optional[RedisOTPStorage] = None
        self._init_redis()

    def _init_redis(self):
        if REDIS_URL:
            try:
                self._redis = RedisOTPStorage(REDIS_URL)
                logger.info("[OTP Storage] Connected successfully to Redis.")
            except Exception as e:
                logger.warning(f"[OTP Storage] Redis connection failed ({e}). Falling back to InMemory storage.")
                self._redis = None
        else:
            logger.info("[OTP Storage] REDIS_URL not configured. Using InMemory storage fallback.")

    @property
    def active_backend(self) -> BaseOTPStorage:
        if self._redis:
            return self._redis
        return self._in_memory

    @property
    def backend_name(self) -> str:
        return "Redis" if self._redis else "InMemory"

    def save_otp(self, email: str, user_id: int, otp: str, ttl_seconds: int = 300) -> bool:
        try:
            return self.active_backend.save_otp(email, user_id, otp, ttl_seconds)
        except Exception as e:
            if self._redis:
                logger.error(f"[OTP Storage] Redis save error ({e}), switching to InMemory fallback.")
                self._redis = None
                return self._in_memory.save_otp(email, user_id, otp, ttl_seconds)
            raise e

    def get_otp(self, email: str) -> Optional[dict]:
        try:
            return self.active_backend.get_otp(email)
        except Exception as e:
            if self._redis:
                logger.error(f"[OTP Storage] Redis get error ({e}), switching to InMemory fallback.")
                self._redis = None
                return self._in_memory.get_otp(email)
            raise e

    def get_remaining_cooldown(self, email: str, cooldown_seconds: int = 60) -> int:
        try:
            return self.active_backend.get_remaining_cooldown(email, cooldown_seconds)
        except Exception as e:
            if self._redis:
                logger.error(f"[OTP Storage] Redis cooldown error ({e}), switching to InMemory fallback.")
                self._redis = None
                return self._in_memory.get_remaining_cooldown(email, cooldown_seconds)
            return 0

    def verify_and_delete_otp(self, email: str, otp_code: str, user_id: int) -> Tuple[bool, str]:
        try:
            return self.active_backend.verify_and_delete_otp(email, otp_code, user_id)
        except Exception as e:
            if self._redis:
                logger.error(f"[OTP Storage] Redis verify error ({e}), switching to InMemory fallback.")
                self._redis = None
                return self._in_memory.verify_and_delete_otp(email, otp_code, user_id)
            raise e

    def delete_otp(self, email: str) -> bool:
        try:
            return self.active_backend.delete_otp(email)
        except Exception as e:
            if self._redis:
                logger.error(f"[OTP Storage] Redis delete error ({e}), switching to InMemory fallback.")
                self._redis = None
                return self._in_memory.delete_otp(email)
            raise e


# Global Singleton Instance
otp_storage = HybridOTPStorage()
