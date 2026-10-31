import sys
import logging
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .trash_cleanup_job import run_cleanup_expired_trash_job

# Đảm bảo an toàn mã hóa UTF-8 trên console Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

# Cấu hình logger hiển thị ra terminal/console
logger = logging.getLogger("unimarket.scheduler")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Biến singleton quản lý Scheduler trong vòng đời FastAPI
_scheduler: Optional[BackgroundScheduler] = None


def get_scheduler() -> BackgroundScheduler:
    """Khởi tạo hoặc lấy instance singleton của BackgroundScheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(
            timezone="Asia/Ho_Chi_Minh",
            job_defaults={
                "coalesce": True,       # Gộp các lần kích hoạt bị bỏ lỡ thành 1 lần chạy
                "max_instances": 1       # Không cho phép 1 job chạy song song nhiều instance gây race condition
            }
        )
    return _scheduler


def register_scheduled_jobs(sched: BackgroundScheduler):
    """
    Đăng ký toàn bộ các Cron Jobs của hệ thống UniMarket:
    1. Dọn dẹp Thùng rác 30 ngày (BR-7): Mặc định chạy vào lúc 02:00 sáng hàng ngày.
    """
    # Job 1: Dọn dẹp thùng rác 30 ngày (BR-7)
    job = sched.add_job(
        run_cleanup_expired_trash_job,
        trigger=CronTrigger(hour=18, minute=11),
        id="cleanup_expired_trash_job",
        name="Quet va xoa vinh vien tin dang thung rac qua han 30 ngay (BR-7)",
        replace_existing=True
    )
    
    next_run = getattr(job, "next_run_time", "Duoc tinh toan khi chay")
    logger.info(f"[SCHEDULER] Da dang ky Job: {job.id}. Next run time: {next_run}")


def start_scheduler():
    """Khởi động Background Scheduler cùng vòng đời ứng dụng FastAPI (lifespan startup)."""
    sched = get_scheduler()
    if not sched.running:
        sched.start()  # Khởi động trước để job.next_run_time được tính toán
        register_scheduled_jobs(sched)
        logger.info("[SCHEDULER] Background Cron Scheduler da khoi dong thanh cong!")
    return sched


def shutdown_scheduler():
    """Tắt an toàn Scheduler khi ứng dụng FastAPI shutdown (lifespan shutdown)."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[SCHEDULER] Background Cron Scheduler da dung an toan.")
        _scheduler = None
