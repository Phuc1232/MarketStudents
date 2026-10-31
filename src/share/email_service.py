import os
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.Core.config import (
    MAIL_FROM,
    MAIL_FROM_NAME,
    MAIL_PASSWORD,
    MAIL_PORT,
    MAIL_SERVER,
    MAIL_USERNAME,
)

logger = logging.getLogger("unimarket.email_service")

# ==============================================================================
# JINJA2 TEMPLATE ENGINE INITIALIZATION
# ==============================================================================
# Path: src/templates/emails
TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates",
    "emails"
)

jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"])
)


def render_email_template(template_name: str, **context: Any) -> str:
    """
    Renders an HTML email template from the templates/emails directory using Jinja2.
    """
    template = jinja_env.get_template(template_name)
    return template.render(**context)


# ==============================================================================
# CORE SMTP DISPATCHER (TRANSPORT LAYER)
# ==============================================================================
def send_email_smtp(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
) -> bool:
    """
    Standard SMTP mail dispatch.
    Works seamlessly with:
    - Gmail SMTP: smtp.gmail.com:587 (STARTTLS) or :465 (SSL)
    - AWS SES SMTP: email-smtp.<region>.amazonaws.com:587
    - Any standard RFC-compliant SMTP server
    """
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        logger.warning(
            f"[EMAIL SERVICE] MAIL_USERNAME or MAIL_PASSWORD not configured. "
            f"Skipping SMTP dispatch to {to_email}."
        )
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"
        msg["To"] = to_email

        # Fallback plain text version
        if not text_content:
            text_content = "Vui lòng mở email trong ứng dụng hỗ trợ HTML để xem đầy đủ nội dung thông báo."
        part_text = MIMEText(text_content, "plain", "utf-8")
        msg.attach(part_text)

        # Rich HTML content
        part_html = MIMEText(html_content, "html", "utf-8")
        msg.attach(part_html)

        # Establish connection based on port
        if MAIL_PORT == 465:
            server = smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT, timeout=12)
        else:
            server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=12)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.sendmail(MAIL_FROM, [to_email], msg.as_string())
        server.quit()

        logger.info(f"[EMAIL SERVICE] Successfully sent email to {to_email} via {MAIL_SERVER}:{MAIL_PORT}")
        return True

    except Exception as e:
        logger.error(f"[EMAIL SERVICE] Failed to send email to {to_email} via {MAIL_SERVER}: {str(e)}")
        return False


# ==============================================================================
# SPECIALIZED BUSINESS DISPATCHERS (CONTEXT-DRIVEN)
# ==============================================================================

def send_student_otp_email(to_email: str, otp_code: str, expire_minutes: int = 5) -> bool:
    """
    Tình huống 1: Gửi mã OTP xác nhận sinh viên (render student_otp.html).
    """
    subject = f"[UniMarket] {otp_code} là mã xác thực tài khoản sinh viên của bạn"
    html_content = render_email_template(
        "student_otp.html",
        otp_code=otp_code,
        expire_minutes=expire_minutes
    )
    text_content = (
        f"Mã OTP xác thực sinh viên UniMarket của bạn là: {otp_code}\n"
        f"Mã có hiệu lực trong {expire_minutes} phút. Vui lòng không chia sẻ mã này với ai."
    )
    return send_email_smtp(to_email, subject, html_content, text_content)


def send_account_warning_email(
    to_email: str,
    user_name: str,
    reason: str,
    details: str = ""
) -> bool:
    """
    Tình huống 2: Gửi email cảnh cáo vi phạm quy chế (render account_warning.html).
    """
    subject = f"[UniMarket] Cảnh báo: Phát hiện vi phạm nội quy tài khoản"
    html_content = render_email_template(
        "account_warning.html",
        user_name=user_name,
        reason=reason,
        details=details
    )
    text_content = (
        f"Xin chào {user_name},\n"
        f"Ban Quản Trị UniMarket gửi cảnh cáo về hành vi vi phạm: {reason}.\n"
        f"Chi tiết: {details}\n"
        f"Nếu tiếp tục tái phạm, tài khoản của bạn sẽ bị khóa vĩnh viễn."
    )
    return send_email_smtp(to_email, subject, html_content, text_content)


def send_account_banned_email(
    to_email: str,
    user_name: str,
    reason: str,
    appeal_link: str = "https://unimarket.vn/identity-verification/appeal"
) -> bool:
    """
    Tình huống 3: Gửi email khi tài khoản bị Admin tạm khóa (render account_banned.html).
    """
    subject = f"[UniMarket] Thông báo quan trọng: Tài khoản của bạn đã bị khóa"
    html_content = render_email_template(
        "account_banned.html",
        user_name=user_name,
        reason=reason,
        appeal_link=appeal_link
    )
    text_content = (
        f"Kính gửi {user_name},\n"
        f"Tài khoản UniMarket của bạn đã bị tạm khóa do: {reason}.\n"
        f"Vui lòng nộp hồ sơ kháng cáo CCCD & SIM chính chủ tại: {appeal_link}"
    )
    return send_email_smtp(to_email, subject, html_content, text_content)


def send_password_reset_otp_email(
    to_email: str,
    user_name: str,
    otp_code: str,
    expire_minutes: int = 5
) -> bool:
    """
    Tình huống 4: Gửi mã OTP đặt lại mật khẩu cho người dùng (render password_reset_otp.html).
    """
    subject = f"[UniMarket] {otp_code} là mã xác nhận đặt lại mật khẩu của bạn"
    html_content = render_email_template(
        "password_reset_otp.html",
        user_name=user_name,
        otp_code=otp_code,
        expire_minutes=expire_minutes
    )
    text_content = (
        f"Xin chào {user_name},\n"
        f"Mã OTP đặt lại mật khẩu UniMarket của bạn là: {otp_code}\n"
        f"Mã có hiệu lực trong {expire_minutes} phút. Tuyệt đối không chia sẻ mã này cho ai khác."
    )
    return send_email_smtp(to_email, subject, html_content, text_content)
