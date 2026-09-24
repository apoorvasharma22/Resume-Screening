from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import get_settings
from app.exceptions import EmailDeliveryError
from app.logging_config import get_logger

log = get_logger(__name__)

DEFAULT_SUBJECT = "You're through to the next stage - {job_title}"
DEFAULT_BODY = """Hi {name},

Thank you for applying for the {job_title} position{company_part}. We reviewed your profile and were impressed by your background - we'd like to move you forward to the next stage.

A member of our recruiting team will reach out shortly to arrange a conversation. In the meantime, feel free to reply to this email with your availability for the coming week.

Warm regards,
The Recruiting Team
"""


def render(name: str, job_title: str, company: str | None, subject: str | None = None, body: str | None = None) -> tuple[str, str]:
    ctx = {"name": name.split()[0] if name else "there", "job_title": job_title, "company_part": f" at {company}" if company else ""}
    return (subject or DEFAULT_SUBJECT).format(**ctx), (body or DEFAULT_BODY).format(**ctx)


def send_email(to: str, subject: str, body: str) -> str:
    s = get_settings()
    if not s.smtp_host:
        log.info("[DRY RUN] would email %s | %s", to, subject)
        return "dry_run"
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            if s.smtp_use_tls:
                smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
    except Exception as exc:
        log.error("SMTP failure sending to %s: %s", to, exc)
        raise EmailDeliveryError(f"Could not send email to {to}: {exc}") from exc
    log.info("Email sent to %s", to)
    return "sent"

