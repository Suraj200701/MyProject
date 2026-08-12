"""Real email delivery over one of two transports.

Resend (HTTPS) is preferred, SMTP is the fallback, and if neither is
configured — e.g. local dev before you've set anything up — emails are
logged instead of sent so the rest of the app keeps working. That last
branch is NOT a mock email system, it's the standard "log instead of
throw when unconfigured" pattern.

Why HTTPS first: most PaaS hosts block outbound SMTP ports (25/465/587)
to curb spam. Render does. On such a host a *correct* smtp.gmail.com
config fails with `SMTPConnectTimeoutError` — packets silently dropped by
a firewall, which reads like a credentials problem but isn't one. Port
443 is never blocked, so an HTTP API is the only transport that reliably
works in production. SMTP is kept because it's still the right tool
locally, where Mailhog/Mailpit need no account and no domain.

The two are deliberately NOT chained on failure: if RESEND_API_KEY is set
and Resend rejects the message, that error surfaces as-is instead of
quietly retrying over SMTP. A transport silently swapping itself out is
far harder to diagnose than one clear error naming who said no.
"""

import logging

import aiosmtplib
import httpx
from email.message import EmailMessage

from config.settings import settings

logger = logging.getLogger("leadmaster.email")

RESEND_ENDPOINT = "https://api.resend.com/emails"


class EmailDeliveryError(RuntimeError):
    """The transport was configured and reachable but refused the message.

    Distinct from the connection-level errors aiosmtplib/httpx raise: this
    means we got an answer and the answer was no (bad key, unverified
    sender domain, recipient rejected).
    """


async def send_email(to: str, subject: str, html_body: str, text_body: str | None = None) -> None:
    if settings.RESEND_API_KEY:
        await _send_via_resend(to, subject, html_body, text_body)
        return

    if settings.SMTP_HOST:
        await _send_via_smtp(to, subject, html_body, text_body)
        return

    logger.info("[email:unconfigured] to=%s subject=%r body=%s", to, subject, html_body)


async def _send_via_resend(to: str, subject: str, html_body: str, text_body: str | None) -> None:
    payload: dict[str, object] = {
        # Resend requires this address to sit on a domain verified in the
        # account. An unverified one is rejected at the API, not silently
        # rewritten — hence the explicit error below rather than a shrug.
        "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>",
        "to": [to],
        "subject": subject,
        "html": html_body,
    }
    if text_body:
        payload["text"] = text_body

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            RESEND_ENDPOINT,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json=payload,
        )

    if response.status_code >= 400:
        # response.text carries Resend's own diagnosis ("domain is not
        # verified", "invalid api key") — worth keeping verbatim, and it
        # contains no secret of ours.
        raise EmailDeliveryError(
            f"Resend refused the message ({response.status_code}): {response.text}"
        )


async def _send_via_smtp(to: str, subject: str, html_body: str, text_body: str | None) -> None:
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
