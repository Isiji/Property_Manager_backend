import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings


def send_email(to_email: str, subject: str, body: str, html_body: str | None = None) -> None:
    if not settings.EMAIL_HOST:
        raise ValueError("EMAIL_HOST is not configured")
    if not settings.EMAIL_PORT:
        raise ValueError("EMAIL_PORT is not configured")
    if not settings.EMAIL_HOST_USER:
        raise ValueError("EMAIL_HOST_USER is not configured")
    if not settings.EMAIL_HOST_PASSWORD:
        raise ValueError("EMAIL_HOST_PASSWORD is not configured")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_HOST_USER
    msg["To"] = to_email

    msg.attach(MIMEText(body, "plain"))

    if html_body:
        msg.attach(MIMEText(html_body, "html"))

    if settings.EMAIL_USE_TLS:
        server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
        server.starttls()
    else:
        server = smtplib.SMTP_SSL(settings.EMAIL_HOST, settings.EMAIL_PORT)

    try:
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        server.sendmail(settings.EMAIL_HOST_USER, [to_email], msg.as_string())
    finally:
        server.quit()