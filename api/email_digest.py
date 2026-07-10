"""
api/email_digest.py — Email Digests for AhmedETAP
=================================================

Daily / weekly summary emails of user activity and notifications.

Endpoints under ``/api/v1/email-digest``:

* ``POST /generate``       — Manually trigger a digest for a user (admin/debug)
* ``GET  /preview/{email}`` — Preview the next digest for a user (no send)
* ``POST /schedule/run``   — Process all scheduled digests (cron call)
* ``GET  /config``         — Show current digest configuration

Digest types
------------
* **daily**: sent at EMAIL_DIGEST_SCHEDULE_DAILY (default 08:00 UTC)
  — includes the user's notifications from the last 24 hours
* **weekly**: sent at EMAIL_DIGEST_SCHEDULE_WEEKLY (default MONDAY_08:00)
  — includes the user's notifications from the last 7 days

Each digest contains:
* Count of new notifications (grouped by type)
* Top 5 unread notifications (title + truncated message)
* Count of completed / failed studies
* Quick-link to the dashboard

Author: ETAP Integration Team
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, EmailStr, Field

from services.email_send_log import get_recent_sends

logger = logging.getLogger("etap.api.email_digest")

router = APIRouter(prefix="/api/v1/email-digest", tags=["email", "digest"])


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _config() -> dict:
    return {
        "enabled": os.getenv("EMAIL_DIGEST_ENABLED", "true").lower() == "true",
        "daily_schedule": os.getenv("EMAIL_DIGEST_SCHEDULE_DAILY", "08:00"),
        "weekly_schedule": os.getenv("EMAIL_DIGEST_SCHEDULE_WEEKLY", "MONDAY_08:00"),
        "timezone": os.getenv("EMAIL_DIGEST_TIMEZONE", "UTC"),
    }


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GenerateDigestRequest(BaseModel):
    email: EmailStr
    period: str = Field(default="daily", pattern=r"^(daily|weekly)$")
    user_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Digest content builder
# ---------------------------------------------------------------------------


async def _build_digest_context(
    email: str,
    period: str,
    user_name: Optional[str] = None,
) -> dict[str, Any]:
    """Build the template context for a user's digest."""
    now = datetime.now(UTC)
    if period == "weekly":
        window_hours = 24 * 7
        period_label = "Weekly"
        period_dates = f"{(now - timedelta(days=7)).strftime('%b %d')} – {now.strftime('%b %d, %Y')}"
    else:
        window_hours = 24
        period_label = "Daily"
        period_dates = now.strftime("%B %d, %Y")

    # Pull from email_send_log for this recipient
    recent = get_recent_sends(limit=500)
    user_sends = [r for r in recent if r.get("recipient", "").lower() == email.lower()]
    user_in_window = [
        r for r in user_sends
        if _parse_iso(r.get("timestamp", "")) >= (now - timedelta(hours=window_hours))
    ]

    # Group by flow
    by_flow: dict[str, int] = {}
    for r in user_in_window:
        flow = r.get("flow", "unknown")
        by_flow[flow] = by_flow.get(flow, 0) + 1

    # Top "notifications" (we approximate using email subjects as proxies)
    items = [
        {
            "title": r.get("subject", "(no subject)"),
            "flow": r.get("flow", "unknown"),
            "timestamp": r.get("timestamp"),
            "success": r.get("success"),
        }
        for r in user_in_window[:10]
    ]

    return {
        "recipient_name": user_name or email.split("@")[0],
        "period_label": period_label,
        "period_dates": period_dates,
        "total_count": len(user_in_window),
        "by_flow": by_flow,
        "items": items,
        "current_year": now.year,
        "app_url": os.getenv("EMAIL_APP_URL", "https://etap-ai-work.vercel.app"),
        "brand_name": os.getenv("EMAIL_BRAND_NAME", "AhmedETAP"),
        "brand_tagline": os.getenv("EMAIL_BRAND_TAGLINE", ""),
        "support_email": os.getenv("EMAIL_SUPPORT_ADDRESS", "support@etap-ai-work.vercel.app"),
    }


def _parse_iso(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/config", summary="Show digest configuration")
async def get_config() -> JSONResponse:
    return JSONResponse(content={"success": True, "config": _config()})


@router.post("/generate", summary="Generate and send a digest now")
async def generate_digest(
    request: Request,
    body: GenerateDigestRequest,
) -> JSONResponse:
    """Manually trigger a digest send for a user."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    if not _config()["enabled"]:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "error": "digests_disabled",
                "trace_id": trace_id,
            },
        )

    ctx = await _build_digest_context(body.email, body.period, body.user_name)

    if ctx["total_count"] == 0:
        return JSONResponse(
            content={
                "success": True,
                "message": f"No activity in the last {body.period} period — digest skipped.",
                "total_count": 0,
                "trace_id": trace_id,
            },
        )

    # Render + send
    try:
        from integrations.resend_email import EmailParams, resend_client
        from services.email_service import _load_template, _render

        template = _load_template("digest.html")
        html = _render(template, **ctx) if template else (
            f"<h2>{ctx['period_label']} Digest</h2>"
            f"<p>{ctx['total_count']} emails sent to you in the last period.</p>"
        )
        subject = f"{ctx['brand_name']} — {ctx['period_label']} Digest ({ctx['total_count']} updates)"

        result = await resend_client.send(EmailParams(
            to=body.email,
            subject=subject,
            html=html,
            text=f"{ctx['period_label']} Digest: {ctx['total_count']} updates. Visit {ctx['app_url']}",
            tags=[{"name": "flow", "value": f"digest_{body.period}"}],
        ))

        return JSONResponse(content={
            "success": result.success,
            "message_id": result.message_id,
            "error": result.error,
            "total_count": ctx["total_count"],
            "by_flow": ctx["by_flow"],
            "trace_id": trace_id,
        })
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(exc), "trace_id": trace_id},
        )


@router.get("/preview/{email}", response_class=HTMLResponse, summary="Preview a user's digest")
async def preview_digest(email: str, period: str = "daily") -> str:
    """Render the digest HTML without sending it (admin/debug)."""
    ctx = await _build_digest_context(email, period)
    from services.email_service import _load_template, _render
    template = _load_template("digest.html")
    if not template:
        return "<h2>Digest template not found</h2>"
    return _render(template, **ctx)


@router.post("/schedule/run", summary="Process scheduled digests (cron call)")
async def run_scheduled_digests(request: Request) -> JSONResponse:
    """Cron entry point — sends digests to all users with recent activity.

    In a production setup, this endpoint is called by:
    * HF Space's internal scheduler (every hour, checks if it's 08:00 UTC)
    * Vercel Cron (configured in vercel.json)
    * GitHub Actions scheduled workflow
    * External cron (curl this endpoint at the scheduled time)

    The endpoint requires ENGINEERING_SERVICE_API_KEY auth (handled by middleware).
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    now = datetime.now(UTC)

    # Determine which digest type to run
    cfg = _config()
    daily_hour, daily_minute = cfg["daily_schedule"].split(":")
    daily_hour, daily_minute = int(daily_hour), int(daily_minute)

    is_daily_run = now.hour == daily_hour and now.minute < 5
    is_weekly_run = (
        now.weekday() == 0  # Monday
        and now.hour == daily_hour
        and now.minute < 5
    )

    if not (is_daily_run or is_weekly_run):
        return JSONResponse(content={
            "success": True,
            "message": "Not scheduled time — skipping.",
            "now": now.isoformat(),
            "daily_time": cfg["daily_schedule"],
            "trace_id": trace_id,
        })

    # Find unique recipients from the last 24h (or 7d for weekly)
    window_hours = 24 * 7 if is_weekly_run else 24
    period = "weekly" if is_weekly_run else "daily"

    recent = get_recent_sends(limit=2000)
    cutoff = now - timedelta(hours=window_hours)
    recipients: set[str] = set()
    for r in recent:
        ts = _parse_iso(r.get("timestamp", ""))
        if ts >= cutoff and r.get("recipient"):
            recipients.add(r["recipient"])

    sent = 0
    failed = 0
    for email in recipients:
        try:
            ctx = await _build_digest_context(email, period)
            if ctx["total_count"] == 0:
                continue
            from integrations.resend_email import EmailParams, resend_client
            from services.email_service import _load_template, _render
            template = _load_template("digest.html")
            html = _render(template, **ctx) if template else ""
            subject = f"{ctx['brand_name']} — {ctx['period_label']} Digest"
            result = await resend_client.send(EmailParams(
                to=email, subject=subject, html=html,
                tags=[{"name": "flow", "value": f"digest_{period}"}],
            ))
            if result.success:
                sent += 1
            else:
                failed += 1
        except Exception as exc:
            logger.warning("digest_send_failed email=%s err=%s", email, exc)
            failed += 1

    return JSONResponse(content={
        "success": True,
        "period": period,
        "recipients_count": len(recipients),
        "sent": sent,
        "failed": failed,
        "trace_id": trace_id,
    })


__all__ = ["router"]
