"""Outgoing email over SMTP with SSL (docs/dev/complaint-email: Titan, smtp.titan.email:465), standard library only.
Not configured (no SMTP_PASSWORD or COMPLAINT_EMAIL_TO) = nothing is sent and nothing fails, like push without
VAPID; DEV leaves it unset so test complaints do not reach support@. Env is read on each call."""
import os
import smtplib
from email.message import EmailMessage

TIMEOUT_SECONDS = 30


def complaint_recipient():
    """Where new complaints are sent, or None when email is not configured."""
    if not os.getenv("SMTP_PASSWORD"):
        return None
    return os.getenv("COMPLAINT_EMAIL_TO") or None


def send(to: str, subject: str, body: str, reply_to: str = None) -> None:
    """Plain-text UTF-8 email from SMTP_USER. Raises on any SMTP / network error (callers run it in the background)."""
    user = os.getenv("SMTP_USER") or "support@sariko.store"
    msg = EmailMessage()
    msg["From"] = f"Sariko <{user}>"
    msg["To"] = to
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)
    host, port = os.getenv("SMTP_HOST") or "smtp.titan.email", int(os.getenv("SMTP_PORT") or 465)
    with smtplib.SMTP_SSL(host, port, timeout=TIMEOUT_SECONDS) as smtp:
        smtp.login(user, os.getenv("SMTP_PASSWORD"))
        smtp.send_message(msg)
