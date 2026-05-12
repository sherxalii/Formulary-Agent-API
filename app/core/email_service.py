import resend
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        if settings.RESEND_API_KEY:
            resend.api_key = settings.RESEND_API_KEY
        self.from_email = settings.SMTP_FROM_EMAIL or "onboarding@resend.dev"

    async def send_email(self, to_email: str, subject: str, body: str, is_html: bool = False) -> bool:
        """Send an email via Resend API."""
        if not settings.RESEND_API_KEY:
            print("\n[EMAIL SERVICE - CONSOLE MODE (No Resend API Key)]")
            print(f"To: {to_email}")
            print(f"Subject: {subject}")
            print(body)
            print("[END EMAIL]\n")
            return True

        try:
            print(f"[RESEND DEBUG] Attempting to send email to {to_email}...")
            # For the onboarding domain, keep it simple
            from_addr = "onboarding@resend.dev"
            
            params = {
                "from": from_addr,
                "to": [to_email],
                "subject": subject,
            }
            if is_html:
                params["html"] = body
            else:
                params["text"] = body

            result = resend.Emails.send(params)
            print(f"[RESEND SUCCESS] Result: {result}")
            logger.info(f"Resend email sent to {to_email}")
            return True
        except Exception as exc:
            print(f"[RESEND ERROR] Failed to send email: {exc}")
            logger.error(f"Resend failure: {exc}")
            return False

    async def send_verification_email(self, email: str, token: str):
        """Send a premium HTML verification email via Resend."""
        verification_link = f"http://localhost:5173/verify?token={token}"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff; color: #1e293b;">
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="color: #10b981; margin: 0;">MediFormulary</h1>
                <p style="color: #64748b; font-size: 0.875rem;">Advanced Clinical Intelligence</p>
            </div>
            <h2 style="color: #0f172a; border-bottom: 2px solid #f1f5f9; padding-bottom: 12px;">Verify Your Identity</h2>
            <p>Welcome to our clinical network. To access the formulary safety tools, please verify your email address.</p>
            <div style="margin: 32px 0; text-align: center;">
                <a href="{verification_link}" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">Verify Account</a>
            </div>
            <p style="font-size: 0.875rem; color: #64748b; background-color: #f8fafc; padding: 12px; border-radius: 6px;">
                <strong>Note:</strong> This link will expire in 24 hours.
            </p>
            <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 32px 0;" />
            <p style="font-size: 0.75rem; color: #94a3b8; text-align: center;">&copy; 2024 MediFormulary Clinical AI. All rights reserved.</p>
        </div>
        """
        return await self.send_email(email, "Verify your MediFormulary account", html, is_html=True)

    async def send_password_reset_email(self, email: str, token: str):
        """Send a premium HTML password reset email via Resend."""
        reset_link = f"http://localhost:5173/reset-password?token={token}"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff; color: #1e293b;">
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="color: #ef4444; margin: 0;">MediFormulary</h1>
                <p style="color: #64748b; font-size: 0.875rem;">Security Notification</p>
            </div>
            <h2 style="color: #0f172a; border-bottom: 2px solid #f1f5f9; padding-bottom: 12px;">Reset Your Password</h2>
            <p>We received a request to reset your password. If this was you, please use the button below to secure your account.</p>
            <div style="margin: 32px 0; text-align: center;">
                <a href="{reset_link}" style="background-color: #0f172a; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">Reset Password</a>
            </div>
            <p style="font-size: 0.875rem; color: #64748b;">
                If you did not request this reset, please ignore this email or contact support immediately.
            </p>
            <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 32px 0;" />
            <p style="font-size: 0.75rem; color: #94a3b8; text-align: center;">&copy; 2024 MediFormulary Security Team.</p>
        </div>
        """
        return await self.send_email(email, "Password Reset Request", html, is_html=True)
