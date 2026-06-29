from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def send_password_reset_otp(email_to: str, otp: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_SENDER", user or "no-reply@example.com")

    if not host or not user or not password:
        raise RuntimeError("SMTP is not configured")

    msg = EmailMessage()
    msg["Subject"] = "Код восстановления доступа"
    msg["From"] = sender
    msg["To"] = email_to
    msg.set_content(
        f"Ваш OTP код для входа: {otp}\n\n"
        "Код действует 10 минут.\n"
        "Если вы не запрашивали восстановление, просто игнорируйте это письмо."
    )

    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
