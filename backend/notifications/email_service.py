"""Real SMTP email delivery.

If SMTP_HOST is unset (e.g. local dev before you've configured a
provider), emails are logged instead of sent so the rest of the app
keeps working — this is NOT a mock email system, it's the standard
"log instead of throw when unconfigured" pattern. Once SMTP_* is set in
.env, every call here goes out over a real SMTP connection.
"""

import logging

import aiosmtplib
from email.message import EmailMessage

from config.settings import settings

logger = logging.getLogger("leadmaster.email")


async def send_email(to: str, subject: str, html_body: str, text_body: str | None = None) -> None:
    if not settings.SMTP_HOST:
        logger.info("[email:unconfigured] to=%s subject=%r body=%s", to, subject, html_body)
        return

    message = EmailMessage()
    message["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text_body or "This email requires an HTML-capable client.")
    message.add_alternative(html_body, subtype="html")

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER or None,
        password=settings.SMTP_PASSWORD or None,
        start_tls=settings.SMTP_USE_TLS,
    )


def _wrapper(title: str, body_html: str) -> str:
    return f"""
    <div style="font-family: -apple-system, Segoe UI, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 24px; color: #1a1a1a;">
      <h2 style="margin-bottom: 8px;">{title}</h2>
      {body_html}
      <p style="margin-top: 32px; font-size: 12px; color: #888;">LeadMaster AI</p>
    </div>
    """


async def send_verification_email(to: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    await send_email(
        to,
        "Verify your LeadMaster AI email",
        _wrapper(
            "Confirm your email address",
            f'<p>Click the link below to verify your email:</p><p><a href="{link}">{link}</a></p>'
            f"<p>This link expires in {settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS} hours.</p>",
        ),
    )


async def send_password_reset_email(to: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    await send_email(
        to,
        "Reset your LeadMaster AI password",
        _wrapper(
            "Reset your password",
            f'<p>Click the link below to choose a new password:</p><p><a href="{link}">{link}</a></p>'
            f"<p>This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes. "
            f"If you didn't request this, you can ignore this email.</p>",
        ),
    )


async def send_otp_email(to: str, code: str, purpose: str) -> None:
    await send_email(
        to,
        f"Your LeadMaster AI verification code: {code}",
        _wrapper(
            "Your verification code",
            f'<p style="font-size: 32px; font-weight: 700; letter-spacing: 4px;">{code}</p>'
            f"<p>This code expires in {settings.OTP_EXPIRE_SECONDS // 60} minutes.</p>",
        ),
    )


async def send_team_invitation_email(to: str, inviter_name: str, org_name: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/signup?invite={token}"
    await send_email(
        to,
        f"{inviter_name} invited you to join {org_name} on LeadMaster AI",
        _wrapper(
            f"You've been invited to {org_name}",
            f'<p>{inviter_name} invited you to collaborate on LeadMaster AI.</p>'
            f'<p><a href="{link}">{link}</a></p>',
        ),
    )
