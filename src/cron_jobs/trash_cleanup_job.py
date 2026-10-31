import sys
import logging
from datetime import datetime
from src.Core.database import SessionLocal
from src.modules.Product.services import cleanup_expired_trash_products, TRASH_EXPIRATION_SECONDS

# Đảm bảo an toàn mã hóa UTF-8 trên console Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

logger = logging.getLogger("unimarket.scheduler")


def run_cleanup_expired_trash_job():
    """
    Tác vụ định kỳ (Cron Job) chạy tự động:
    Quét và dọn dẹp triệt để các tin đăng đã nằm trong thùng rác quá hạn (30 ngày theo quy tắc BR-7, AC-12).
    Mỗi phiên chạy tự mở một DB Session độc lập và đóng an toàn khi hoàn tất.
    """
    db = SessionLocal()
    try:
        result = cleanup_expired_trash_products(db=db, expired_seconds=TRASH_EXPIRATION_SECONDS)
        if result.cleaned_products_count > 0:
            logger.info(
                f"[CRON BR-7] Hoan tat don dep thanh cong {result.cleaned_products_count} tin dang. "
                f"Danh sach ID: {result.cleaned_product_ids}"
            )
        else:
            logger.info("[CRON BR-7] Thung rac sach, khong co tin dang nao bi qua han.")
    except Exception as exc:
        print(f"-> LOI           : {exc}")
        logger.error(f"[CRON BR-7] Loi trong qua trinh don dep thung rac tu dong: {exc}", exc_info=True)
    finally:
        db.close()
        print("=" * 65 + "\n")
