import ssl
import smtplib
from email.message import EmailMessage
from app.core.config import settings


class EmailService:
    def __init__(self):
        self.server = settings.SMTP_SERVER
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USERNAME
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
        self.use_tls = settings.SMTP_USE_TLS

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        if not self.server or not self.username or not self.password:
            # Console mode fallback for local development.
            print("\n[EMAIL SERVICE - CONSOLE MODE]")
            print(f"To: {to_email}")
            print(f"Subject: {subject}")
            print(body)
            print("[END EMAIL]\n")
            return True

        message = EmailMessage()
        message["From"] = self.from_email
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        try:
            if self.use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(self.server, self.port, timeout=10) as smtp:
                    smtp.starttls(context=context)
                    smtp.login(self.username, self.password)
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(self.server, self.port, timeout=10) as smtp:
                    smtp.login(self.username, self.password)
                    smtp.send_message(message)
            return True
        except Exception as exc:
            print(f"Failed to send email: {exc}")
            return False
