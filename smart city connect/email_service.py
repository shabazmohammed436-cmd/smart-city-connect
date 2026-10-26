import smtplib
from email.message import EmailMessage

from flask import current_app


def send_email(to_address: str, subject: str, body: str) -> tuple[bool, str]:
    config = current_app.config
    server = config.get("MAIL_SERVER")
    username = config.get("MAIL_USERNAME")
    password = config.get("MAIL_PASSWORD")
    if not (server and username and password):
        return False, "Email delivery is not configured."

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.get("MAIL_FROM")
    message["To"] = to_address
    message.set_content(body)

    try:
        port = int(config.get("MAIL_PORT") or 587)
        with smtplib.SMTP(server, port, timeout=20) as smtp:
            if config.get("MAIL_USE_TLS"):
                smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(message)
        return True, "sent"
    except Exception:
        return False, "The email service could not send the message. Please try the local verification option."
