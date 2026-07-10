"""
services/email_service.py — High-level Email Service for AhmedETAP
=================================================================

Layered on top of ``integrations/resend_email.py`` to provide domain-specific
email flows used by authentication, MFA, notifications, and operations.

Public API
----------
Auth & MFA flows
    send_email_otp(email, code, purpose)        — OTP for signup / login / 2FA
    send_password_reset(email, reset_link, name) — forgot-password email
    send_welcome(email, name)                   — post-registration welcome
    send_email_verification(email, verify_link) — verify email ownership
    send_login_alert(email, ip, user_agent, ts) — new-device / new-IP alert
    send_account_lockout(email, unlock_at)      — locked-out notification

Notification flows
    send_notification_email(email, notif)       — generic in-app notification
    send_study_complete_email(email, study)     — long-running study done
    send_study_failed_email(email, study, err)  — study errored
    send_role_change_email(email, role, by)     — RBAC role change
    send_password_change_email(email)           — password changed

Operational flows
    send_critical_alert(email, title, body)     — admin/system critical alert
    send_batch_complete(email, summary)         — import/export done

Each function returns ``EmailResult`` (never raises).

Templates
---------
HTML templates live in ``templates/emails/*.html`` and use simple
``{{ placeholder }}`` substitution (no Jinja2 dependency).

Author: ETAP Integration Team
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from integrations.resend_email import EmailParams, EmailResult, resend_client

logger = logging.getLogger("etap.email_service")

# ---------------------------------------------------------------------------
# Template loader
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"

# Cache templates in memory after first read
_template_cache: dict[str, str] = {}


def _load_template(name: str) -> Optional[str]:
    """Load an HTML template by filename (e.g. 'otp.html')."""
    if name in _template_cache:
        return _template_cache[name]
    path = _TEMPLATES_DIR / name
    if not path.exists():
        logger.error("email_template_missing name=%s path=%s", name, path)
        return None
    try:
        content = path.read_text(encoding="utf-8")
        _template_cache[name] = content
        return content
    except OSError as exc:
        logger.error("email_template_read_failed name=%s err=%s", name, exc)
        return None


def _render(template: str, **kwargs: Any) -> str:
    """Render a template with {{ key }} substitution."""
    out = template
    for key, value in kwargs.items():
        placeholder = "{{ " + key + " }}"
        out = out.replace(placeholder, str(value))
        # Also support no-space variant {{key}}
        out = out.replace("{{" + key + "}}", str(value))
    return out


# ---------------------------------------------------------------------------
# Brand config
# ---------------------------------------------------------------------------

_BRAND_NAME = os.getenv("EMAIL_BRAND_NAME", "AhmedETAP")
_BRAND_TAGLINE = os.getenv("EMAIL_BRAND_TAGLINE", "Enterprise Engineering Intelligence Platform")
_SUPPORT_EMAIL = os.getenv("EMAIL_SUPPORT_ADDRESS", "support@etap-ai-work.vercel.app")
_APP_URL = os.getenv("EMAIL_APP_URL", "https://etap-ai-work.vercel.app")


def _common_context(**extra: Any) -> dict[str, Any]:
    """Return common template context (brand, year, links)."""
    ctx = {
        "brand_name": _BRAND_NAME,
        "brand_tagline": _BRAND_TAGLINE,
        "support_email": _SUPPORT_EMAIL,
        "app_url": _APP_URL,
        "year": datetime.now(timezone.utc).year,
    }
    ctx.update(extra)
    return ctx


# ---------------------------------------------------------------------------
# Auth & MFA flows
# ---------------------------------------------------------------------------


async def send_email_otp(
    email: str,
    code: str,
    purpose: str = "login",
    user_name: Optional[str] = None,
    ttl_minutes: int = 10,
) -> EmailResult:
    """Send an OTP code by email.

    Parameters
    ----------
    email : str
        Recipient email.
    code : str
        6-digit OTP code (already validated by caller).
    purpose : str
        One of: login, signup, password_reset, mfa, sensitive_action.
        Drives the subject line and template text.
    user_name : Optional[str]
        Recipient display name (falls back to email).
    ttl_minutes : int
        Code validity shown to user (default 10).
    """
    purpose_labels = {
        "login": "Login Verification Code",
        "signup": "Account Verification Code",
        "password_reset": "Password Reset Code",
        "mfa": "Two-Factor Authentication Code",
        "sensitive_action": "Authorization Code",
    }
    subject = f"{_BRAND_NAME} — {purpose_labels.get(purpose, 'Verification Code')}"

    template = _load_template("otp.html")
    ctx = _common_context(
        recipient_name=user_name or email.split("@")[0],
        otp_code=code,
        purpose=purpose,
        purpose_label=purpose_labels.get(purpose, "Verification"),
        ttl_minutes=ttl_minutes,
        current_year=datetime.now(timezone.utc).year,
    )
    html = _render(template, **ctx) if template else _fallback_otp_html(code, purpose, ttl_minutes)
    text = (
        f"Your {_BRAND_NAME} verification code is: {code}\n"
        f"Purpose: {purpose}\n"
        f"This code expires in {ttl_minutes} minutes.\n"
        f"If you did not request this, ignore this email.\n"
    )

    return await resend_client.send(EmailParams(
        to=email,
        subject=subject,
        html=html,
        text=text,
        tags=[{"name": "flow", "value": "otp"}, {"name": "purpose", "value": purpose}],
    ))


async def send_password_reset(
    email: str,
    reset_link: str,
    user_name: Optional[str] = None,
    ttl_minutes: int = 30,
) -> EmailResult:
    """Send a password reset email with a one-time link."""
    subject = f"{_BRAND_NAME} — Reset Your Password"
    template = _load_template("password_reset.html")
    ctx = _common_context(
        recipient_name=user_name or email.split("@")[0],
        reset_link=reset_link,
        ttl_minutes=ttl_minutes,
        current_year=datetime.now(timezone.utc).year,
    )
    html = _render(template, **ctx) if template else _fallback_reset_html(reset_link, ttl_minutes)
    text = (
        f"Reset your {_BRAND_NAME} password:\n\n"
        f"{reset_link}\n\n"
        f"This link expires in {ttl_minutes} minutes.\n"
        f"If you did not request a reset, ignore this email.\n"
    )
    return await resend_client.send(EmailParams(
        to=email,
        subject=subject,
        html=html,
        text=text,
        tags=[{"name": "flow", "value": "password_reset"}],
    ))


async def send_welcome(email: str, user_name: Optional[str] = None) -> EmailResult:
    """Send a welcome email after successful registration."""
    subject = f"Welcome to {_BRAND_NAME}!"
    template = _load_template("welcome.html")
    ctx = _common_context(
        recipient_name=user_name or email.split("@")[0],
        login_url=_APP_URL + "/login",
        docs_url=_APP_URL + "/docs",
        current_year=datetime.now(timezone.utc).year,
    )
    html = _render(template, **ctx) if template else _fallback_welcome_html(user_name or email)
    text = (
        f"Welcome to {_BRAND_NAME}!\n\n"
        f"Your account has been created. Visit {_APP_URL}/login to get started.\n"
        f"For help, contact {_SUPPORT_EMAIL}.\n"
    )
    return await resend_client.send(EmailParams(
        to=email,
        subject=subject,
        html=html,
        text=text,
        tags=[{"name": "flow", "value": "welcome"}],
    ))


async def send_email_verification(
    email: str,
    verify_link: str,
    user_name: Optional[str] = None,
) -> EmailResult:
    """Send a 'verify your email' link email (post-signup)."""
    subject = f"{_BRAND_NAME} — Verify Your Email Address"
    template = _load_template("verify_email.html")
    ctx = _common_context(
        recipient_name=user_name or email.split("@")[0],
        verify_link=verify_link,
        current_year=datetime.now(timezone.utc).year,
    )
    html = _render(template, **ctx) if template else _fallback_verify_html(verify_link)
    text = (
        f"Verify your email address:\n\n"
        f"{verify_link}\n\n"
        f"This link expires in 24 hours.\n"
    )
    return await resend_client.send(EmailParams(
        to=email,
        subject=subject,
        html=html,
        text=text,
        tags=[{"name": "flow", "value": "email_verification"}],
    ))


async def send_login_alert(
    email: str,
    ip: str,
    user_agent: str,
    timestamp: Optional[datetime] = None,
    user_name: Optional[str] = None,
    location: Optional[str] = None,
) -> EmailResult:
    """Send a 'new login' security alert."""
    ts = timestamp or datetime.now(timezone.utc)
    subject = f"{_BRAND_NAME} — New Login to Your Account"
    template = _load_template("login_alert.html")
    ctx = _common_context(
        recipient_name=user_name or email.split("@")[0],
        ip_address=ip,
        user_agent=user_agent[:200],  # truncate very long UAs
        login_time=ts.strftime("%Y-%m-%d %H:%M:%S UTC"),
        location=location or "Unknown",
        security_url=_APP_URL + "/settings/security",
        current_year=datetime.now(timezone.utc).year,
    )
    html = _render(template, **ctx) if template else _fallback_login_alert_html(ip, user_agent, ts)
    text = (
        f"New login to your {_BRAND_NAME} account:\n\n"
        f"Time: {ts.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"IP: {ip}\n"
        f"Device: {user_agent[:200]}\n\n"
        f"If this was you, no action is needed.\n"
        f"If not, change your password immediately at {_APP_URL}/settings/security\n"
    )
    return await resend_client.send(EmailParams(
        to=email,
        subject=subject,
        html=html,
        text=text,
        tags=[{"name": "flow", "value": "login_alert"}],
    ))


async def send_account_lockout(
    email: str,
    unlock_at: datetime,
    user_name: Optional[str] = None,
) -> EmailResult:
    """Notify a user their account was locked due to failed login attempts."""
    subject = f"{_BRAND_NAME} — Account Temporarily Locked"
    template = _load_template("lockout.html")
    ctx = _common_context(
        recipient_name=user_name or email.split("@")[0],
        unlock_time=unlock_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        support_email=_SUPPORT_EMAIL,
        current_year=datetime.now(timezone.utc).year,
    )
    html = _render(template, **ctx) if template else _fallback_lockout_html(unlock_at)
    text = (
        f"Your {_BRAND_NAME} account has been temporarily locked due to "
        f"multiple failed login attempts.\n\n"
        f"It will automatically unlock at: {unlock_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"If this was not you, contact {_SUPPORT_EMAIL} immediately.\n"
    )
    return await resend_client.send(EmailParams(
        to=email,
        subject=subject,
        html=html,
        text=text,
        tags=[{"name": "flow", "value": "lockout"}],
    ))


# ---------------------------------------------------------------------------
# Notification flows
# ---------------------------------------------------------------------------


async def send_notification_email(
    email: str,
    title: str,
    message: str,
    priority: str = "normal",
    user_name: Optional[str] = None,
    action_url: Optional[str] = None,
    action_label: Optional[str] = None,
) -> EmailResult:
    """Send a generic notification email (for ``requires_email=True``)."""
    subject = f"[{_BRAND_NAME}] {title}"
    template = _load_template("notification.html")
    ctx = _common_context(
        recipient_name=user_name or email.split("@")[0],
        notification_title=title,
        notification_message=message,
        priority=priority.upper(),
        action_url=action_url or _APP_URL,
        action_label=action_label or "Open Dashboard",
        current_year=datetime.now(timezone.utc).year,
    )
    html = _render(template, **ctx) if template else _fallback_notification_html(title, message)
    text = f"{title}\n\n{message}\n\nOpen: {action_url or _APP_URL}\n"
    return await resend_client.send(EmailParams(
        to=email,
        subject=subject,
        html=html,
        text=text,
        tags=[
            {"name": "flow", "value": "notification"},
            {"name": "priority", "value": priority},
        ],
    ))


async def send_study_complete_email(
    email: str,
    study_name: str,
    study_url: str,
    user_name: Optional[str] = None,
    duration_sec: Optional[float] = None,
) -> EmailResult:
    """Notify a user that their long-running engineering study finished."""
    subject = f"{_BRAND_NAME} — Study Completed: {study_name}"
    template = _load_template("study_complete.html")
    duration_str = f"{duration_sec:.1f}s" if duration_sec else "—"
    ctx = _common_context(
        recipient_name=user_name or email.split("@")[0],
        study_name=study_name,
        study_url=study_url,
        duration=duration_str,
        completed_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        current_year=datetime.now(timezone.utc).year,
    )
    html = _render(template, **ctx) if template else _fallback_study_html(study_name, study_url, completed=True)
    text = (
        f"Your study '{study_name}' has completed.\n"
        f"Duration: {duration_str}\n"
        f"View results: {study_url}\n"
    )
    return await resend_client.send(EmailParams(
        to=email,
        subject=subject,
        html=html,
        text=text,
        tags=[{"name": "flow", "value": "study_complete"}],
    ))


async def send_study_failed_email(
    email: str,
    study_name: str,
    error_message: str,
    user_name: Optional[str] = None,
) -> EmailResult:
    """Notify a user their study failed."""
    subject = f"{_BRAND_NAME} — Study Failed: {study_name}"
    template = _load_template("study_failed.html")
    ctx = _common_context(
        recipient_name=user_name or email.split("@")[0],
        study_name=study_name,
        error_message=error_message[:500],
        failed_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        support_email=_SUPPORT_EMAIL,
        current_year=datetime.now(timezone.utc).year,
    )
    html = _render(template, **ctx) if template else _fallback_study_html(study_name, "", completed=False, err=error_message)
    text = (
        f"Your study '{study_name}' failed.\n"
        f"Error: {error_message[:500]}\n"
        f"For help, contact {_SUPPORT_EMAIL}\n"
    )
    return await resend_client.send(EmailParams(
        to=email,
        subject=subject,
        html=html,
        text=text,
        tags=[{"name": "flow", "value": "study_failed"}],
    ))


async def send_role_change_email(
    email: str,
    new_role: str,
    changed_by: str,
    user_name: Optional[str] = None,
) -> EmailResult:
    """Notify a user their RBAC role was changed."""
    subject = f"{_BRAND_NAME} — Your Role Has Been Updated"
    template = _load_template("role_change.html")
    ctx = _common_context(
        recipient_name=user_name or email.split("@")[0],
        new_role=new_role,
        changed_by=changed_by,
        changed_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        current_year=datetime.now(timezone.utc).year,
    )
    html = _render(template, **ctx) if template else _fallback_role_html(new_role, changed_by)
    text = (
        f"Your {_BRAND_NAME} role has been updated to: {new_role}\n"
        f"Changed by: {changed_by}\n"
        f"If this is unexpected, contact {_SUPPORT_EMAIL}.\n"
    )
    return await resend_client.send(EmailParams(
        to=email,
        subject=subject,
        html=html,
        text=text,
        tags=[{"name": "flow", "value": "role_change"}],
    ))


async def send_password_change_email(
    email: str,
    user_name: Optional[str] = None,
    ip: Optional[str] = None,
) -> EmailResult:
    """Confirm a password change."""
    subject = f"{_BRAND_NAME} — Your Password Was Changed"
    template = _load_template("password_change.html")
    ctx = _common_context(
        recipient_name=user_name or email.split("@")[0],
        changed_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        ip_address=ip or "unknown",
        security_url=_APP_URL + "/settings/security",
        support_email=_SUPPORT_EMAIL,
        current_year=datetime.now(timezone.utc).year,
    )
    html = _render(template, **ctx) if template else _fallback_pwd_change_html(ip)
    text = (
        f"Your {_BRAND_NAME} password was changed at "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}.\n"
        f"If this was not you, contact {_SUPPORT_EMAIL} immediately.\n"
    )
    return await resend_client.send(EmailParams(
        to=email,
        subject=subject,
        html=html,
        text=text,
        tags=[{"name": "flow", "value": "password_change"}],
    ))


# ---------------------------------------------------------------------------
# Operational flows
# ---------------------------------------------------------------------------


async def send_critical_alert(
    email: str,
    title: str,
    body: str,
    dashboard_url: Optional[str] = None,
) -> EmailResult:
    """Send a critical system alert to an admin/ops recipient."""
    subject = f"[CRITICAL] {_BRAND_NAME} — {title}"
    template = _load_template("critical_alert.html")
    ctx = _common_context(
        recipient_name="Administrator",
        alert_title=title,
        alert_body=body,
        dashboard_url=dashboard_url or _APP_URL + "/admin",
        triggered_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        current_year=datetime.now(timezone.utc).year,
    )
    html = _render(template, **ctx) if template else _fallback_critical_html(title, body)
    text = (
        f"CRITICAL ALERT\n\n"
        f"Title: {title}\n"
        f"Body: {body}\n"
        f"Time: {datetime.now(timezone.utc).isoformat()}\n"
    )
    return await resend_client.send(EmailParams(
        to=email,
        subject=subject,
        html=html,
        text=text,
        tags=[{"name": "flow", "value": "critical_alert"}, {"name": "priority", "value": "critical"}],
    ))


# ---------------------------------------------------------------------------
# Fallback HTML (used if template files are missing)
# ---------------------------------------------------------------------------


def _fallback_otp_html(code: str, purpose: str, ttl: int) -> str:
    return f"""<!doctype html><html><body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">
<h2 style="color:#1e40af;">{_BRAND_NAME}</h2>
<p>Your verification code is:</p>
<h1 style="font-size:36px;letter-spacing:8px;color:#1e40af;">{code}</h1>
<p>Purpose: {purpose}</p>
<p>This code expires in {ttl} minutes.</p>
<p style="color:#6b7280;font-size:12px;margin-top:32px;">If you did not request this, ignore this email.</p>
</body></html>"""


def _fallback_reset_html(link: str, ttl: int) -> str:
    return f"""<!doctype html><html><body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">
<h2 style="color:#1e40af;">{_BRAND_NAME}</h2>
<p>Reset your password by clicking the button below:</p>
<p><a href="{link}" style="display:inline-block;background:#1e40af;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;">Reset Password</a></p>
<p style="color:#6b7280;font-size:12px;">Or copy this link: {link}</p>
<p>This link expires in {ttl} minutes.</p>
</body></html>"""


def _fallback_welcome_html(name: str) -> str:
    return f"""<!doctype html><html><body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">
<h2 style="color:#1e40af;">Welcome to {_BRAND_NAME}!</h2>
<p>Hi {name},</p>
<p>Your account has been created. Visit {_APP_URL}/login to get started.</p>
</body></html>"""


def _fallback_verify_html(link: str) -> str:
    return f"""<!doctype html><html><body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">
<h2 style="color:#1e40af;">{_BRAND_NAME}</h2>
<p>Verify your email address:</p>
<p><a href="{link}" style="display:inline-block;background:#1e40af;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;">Verify Email</a></p>
</body></html>"""


def _fallback_login_alert_html(ip: str, ua: str, ts: datetime) -> str:
    return f"""<!doctype html><html><body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">
<h2 style="color:#dc2626;">New Login to {_BRAND_NAME}</h2>
<p>Time: {ts.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
<p>IP: {ip}</p>
<p>Device: {ua[:200]}</p>
<p>If this was not you, change your password immediately.</p>
</body></html>"""


def _fallback_lockout_html(unlock_at: datetime) -> str:
    return f"""<!doctype html><html><body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">
<h2 style="color:#dc2626;">Account Locked</h2>
<p>Your {_BRAND_NAME} account has been temporarily locked due to multiple failed login attempts.</p>
<p>It will automatically unlock at: <strong>{unlock_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</strong></p>
</body></html>"""


def _fallback_notification_html(title: str, message: str) -> str:
    return f"""<!doctype html><html><body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">
<h3>{title}</h3>
<p>{message}</p>
</body></html>"""


def _fallback_study_html(name: str, url: str, completed: bool, err: str = "") -> str:
    status = "Completed" if completed else "Failed"
    color = "#16a34a" if completed else "#dc2626"
    body = f'<p><a href="{url}">View results</a></p>' if completed else f'<p>Error: {err[:200]}</p>'
    return f"""<!doctype html><html><body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">
<h2 style="color:{color};">Study {status}: {name}</h2>
{body}
</body></html>"""


def _fallback_role_html(role: str, by: str) -> str:
    return f"""<!doctype html><html><body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">
<h2>Role Updated</h2>
<p>Your role has been updated to: <strong>{role}</strong></p>
<p>Changed by: {by}</p>
</body></html>"""


def _fallback_pwd_change_html(ip: Optional[str]) -> str:
    return f"""<!doctype html><html><body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">
<h2>Password Changed</h2>
<p>Your {_BRAND_NAME} password was changed.</p>
<p>IP: {ip or 'unknown'}</p>
<p>If this was not you, contact support immediately.</p>
</body></html>"""


def _fallback_critical_html(title: str, body: str) -> str:
    return f"""<!doctype html><html><body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;border-left:4px solid #dc2626;">
<h2 style="color:#dc2626;">CRITICAL ALERT</h2>
<h3>{title}</h3>
<p>{body}</p>
</body></html>"""


__all__ = [
    # Auth & MFA
    "send_email_otp",
    "send_password_reset",
    "send_welcome",
    "send_email_verification",
    "send_login_alert",
    "send_account_lockout",
    # Notifications
    "send_notification_email",
    "send_study_complete_email",
    "send_study_failed_email",
    "send_role_change_email",
    "send_password_change_email",
    # Operational
    "send_critical_alert",
]
