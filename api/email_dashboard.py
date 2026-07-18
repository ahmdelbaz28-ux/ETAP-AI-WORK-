"""
api/email_dashboard.py — Email Monitoring Dashboard for AhmedETAP
=================================================================

Admin-only dashboard to monitor email sends, success rates, errors, and trends.

Endpoints under ``/api/v1/email-dashboard``:

* ``GET /``              — HTML dashboard page (admin-only)
* ``GET /api/stats``     — JSON stats for the last N hours (default 24h)
* ``GET /api/recent``    — JSON list of recent sends
* ``GET /api/by-day``    — JSON daily breakdown for last N days (default 7)
* ``GET /api/record/{id}`` — Single record detail
* ``POST /api/clear``    — Clear logs older than N hours (admin only)
* ``GET /api/config``    — Current Resend config (no secrets exposed)

Authentication
--------------
Endpoints require a valid JWT with one of the roles in
``EMAIL_DASHBOARD_ADMIN_ROLES`` (default: admin, super_admin).

Author: ETAP Integration Team
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger("etap.api.email_dashboard")

router = APIRouter(prefix="/api/v1/email-dashboard", tags=["email", "dashboard"])

# Admin roles allowed to view dashboard
# Includes 'service' for API-key auth in dev mode (E-06 rev2 compatibility)
_ADMIN_ROLES = {
    r.strip()
    for r in os.getenv(
        "EMAIL_DASHBOARD_ADMIN_ROLES",
        "admin,super_admin,service",
    ).split(",")
    if r.strip()
}


# ---------------------------------------------------------------------------
# Auth dependency (best-effort — uses existing get_current_user_from_header)
# ---------------------------------------------------------------------------


def _require_admin(request: Request) -> dict:
    """Require admin role. Returns user info dict.

    Accepts either:
    1. X-API-Key header (service key) — for automation/CI/Postman tests
    2. JWT Bearer token (Authorization: Bearer <token>) — for human users
    3. Dev mode (EMAIL_DASHBOARD_DEV_OPEN=true) — no auth required
    """
    # ─── Method 1: X-API-Key (service key for automation) ────────────────
    from api._test_mode import get_api_key_auth

    api_key_auth = get_api_key_auth(request)
    if api_key_auth:
        return api_key_auth

    # ─── Method 2: JWT Bearer token ──────────────────────────────────────
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            import jwt as pyjwt

            from api.dependencies import JWT_ALGORITHM, JWT_SECRET_KEY

            token = auth_header[7:]
            payload = pyjwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM],
            )
            user_id = payload.get("sub") or payload.get("user_id")
            user_role = payload.get("role", "")

            if user_role not in _ADMIN_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Admin role required (your role: {user_role})",
                )
            return {"user_id": user_id, "role": user_role, "auth_method": "jwt"}
        except HTTPException:
            raise
        except Exception as jwt_err:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid JWT token: {jwt_err}",
            ) from jwt_err

    # ─── Method 3: Dev mode (no auth) ────────────────────────────────────
    if os.getenv("EMAIL_DASHBOARD_DEV_OPEN", "false").lower() == "true":
        return {"user_id": "dev", "role": "dev", "auth_method": "dev"}

    # ─── No valid auth ───────────────────────────────────────────────────
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Send either 'X-API-Key' header or 'Authorization: Bearer <jwt>'",
    )


# ---------------------------------------------------------------------------
# JSON API endpoints
# ---------------------------------------------------------------------------


@router.get("/api/stats", summary="Email send statistics")
async def get_stats(
    request: Request,
    window_hours: int = 24,
    _: dict = Depends(_require_admin),
) -> JSONResponse:
    """Aggregate stats for the last `window_hours`."""
    from services.email_send_log import get_send_stats

    return JSONResponse(
        content={
            "success": True,
            "stats": get_send_stats(window_hours=window_hours),
        }
    )


@router.get("/api/recent", summary="Recent email sends")
async def get_recent(
    request: Request,
    limit: int = 100,
    flow: Optional[str] = None,
    _: dict = Depends(_require_admin),
) -> JSONResponse:
    """Recent send records (newest first)."""
    from services.email_send_log import get_recent_sends

    return JSONResponse(
        content={
            "success": True,
            "records": get_recent_sends(limit=limit, flow=flow),
        }
    )


@router.get("/api/by-day", summary="Daily send counts for the last N days")
async def get_by_day(
    request: Request,
    days: int = 7,
    _: dict = Depends(_require_admin),
) -> JSONResponse:
    from services.email_send_log import get_send_count_by_day

    return JSONResponse(
        content={
            "success": True,
            "days": get_send_count_by_day(days=days),
        }
    )


@router.get("/api/record/{record_id}", summary="Single record detail", responses={404: {"description": "Record not found"}})
async def get_record(
    record_id: str,
    request: Request,
    _: dict = Depends(_require_admin),
) -> JSONResponse:
    from services.email_send_log import get_record_by_id

    record = get_record_by_id(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return JSONResponse(content={"success": True, "record": record})


@router.post("/api/clear", summary="Clear old log records")
async def clear_old(
    request: Request,
    max_age_hours: int = 720,
    _: dict = Depends(_require_admin),
) -> JSONResponse:
    from services.email_send_log import clear_old_records

    removed = clear_old_records(max_age_hours=max_age_hours)
    return JSONResponse(
        content={
            "success": True,
            "removed": removed,
            "max_age_hours": max_age_hours,
        }
    )


@router.get("/api/config", summary="Current Resend config (no secrets)")
async def get_config(
    request: Request,
    _: dict = Depends(_require_admin),
) -> JSONResponse:
    """Return non-secret Resend configuration for diagnostic purposes."""
    return JSONResponse(
        content={
            "success": True,
            "config": {
                "RESEND_ENABLED": os.getenv("RESEND_ENABLED", "true"),
                "RESEND_FROM_EMAIL": os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev"),
                "RESEND_FROM_NAME": os.getenv("RESEND_FROM_NAME", "AhmedETAP"),
                "RESEND_REPLY_TO": os.getenv("RESEND_REPLY_TO", ""),
                "RESEND_TIMEOUT_SECONDS": os.getenv("RESEND_TIMEOUT_SECONDS", "15"),
                "RESEND_MAX_RETRIES": os.getenv("RESEND_MAX_RETRIES", "3"),
                "RESEND_RATE_LIMIT_MAX": os.getenv("RESEND_RATE_LIMIT_MAX", "10"),
                "RESEND_RATE_LIMIT_WINDOW": os.getenv("RESEND_RATE_LIMIT_WINDOW", "60"),
                "RESEND_LOGIN_ALERTS_ENABLED": os.getenv("RESEND_LOGIN_ALERTS_ENABLED", "false"),
                "RESEND_LOCKOUT_ALERTS_ENABLED": os.getenv("RESEND_LOCKOUT_ALERTS_ENABLED", "true"),
                "RESEND_WELCOME_EMAIL_ENABLED": os.getenv("RESEND_WELCOME_EMAIL_ENABLED", "true"),
                "RESEND_NOTIFICATION_EMAILS_ENABLED": os.getenv(
                    "RESEND_NOTIFICATION_EMAILS_ENABLED", "true"
                ),
                "OTP_TTL_SECONDS": os.getenv("OTP_TTL_SECONDS", "600"),
                "MAGIC_LINK_TTL_SECONDS": os.getenv("MAGIC_LINK_TTL_SECONDS", "900"),
                "EMAIL_DIGEST_ENABLED": os.getenv("EMAIL_DIGEST_ENABLED", "true"),
                "EMAIL_DIGEST_SCHEDULE_DAILY": os.getenv("EMAIL_DIGEST_SCHEDULE_DAILY", "08:00"),
                "EMAIL_BRAND_NAME": os.getenv("EMAIL_BRAND_NAME", "AhmedETAP"),
                "EMAIL_APP_URL": os.getenv("EMAIL_APP_URL", "https://etap-ai-work.vercel.app"),
                # API key is masked
                "RESEND_API_KEY_SET": "yes" if os.getenv("RESEND_API_KEY") else "no",
            },
        }
    )


# ---------------------------------------------------------------------------
# HTML dashboard page
# ---------------------------------------------------------------------------


_DASHBOARD_HTML = """<!doctype html>
<html lang="en" dir="ltr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AhmedETAP — Email Dashboard</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f3f4f6; color: #111827; line-height: 1.5;
    }
    .header {
      background: linear-gradient(135deg, #facc15 0%, #ef4444 100%);
      padding: 24px 32px; color: #1f2937;
    }
    .header h1 { font-size: 24px; font-weight: 700; }
    .header .sub { font-size: 13px; margin-top: 4px; font-weight: 500; }
    .container { max-width: 1400px; margin: 0 auto; padding: 24px; }
    .grid { display: grid; gap: 16px; }
    .grid-4 { grid-template-columns: repeat(4, 1fr); }
    .grid-2 { grid-template-columns: repeat(2, 1fr); }
    @media (max-width: 1024px) {
      .grid-4 { grid-template-columns: repeat(2, 1fr); }
      .grid-2 { grid-template-columns: 1fr; }
    }
    .card {
      background: #fff; border-radius: 12px; padding: 20px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .stat-card .label {
      font-size: 11px; text-transform: uppercase;
      letter-spacing: 0.5px; color: #6b7280; font-weight: 600;
    }
    .stat-card .value { font-size: 32px; font-weight: 700; color: #111827; margin-top: 6px; }
    .stat-card.success .value { color: #16a34a; }
    .stat-card.danger .value { color: #dc2626; }
    .stat-card.warning .value { color: #d97706; }
    .stat-card .sub { font-size: 12px; color: #6b7280; margin-top: 4px; }
    .card h3 { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th { text-align: left; padding: 8px 10px; border-bottom: 2px solid #e5e7eb; color: #6b7280; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }
    td { padding: 8px 10px; border-bottom: 1px solid #f3f4f6; }
    tr:hover td { background: #f9fafb; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
    .badge-success { background: #dcfce7; color: #16a34a; }
    .badge-failed { background: #fef2f2; color: #dc2626; }
    .badge-flow { background: #eff6ff; color: #1e40af; }
    .controls { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
    .controls select, .controls input { padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; }
    .controls button { padding: 6px 14px; background: #1e40af; color: white; border: 0; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500; }
    .controls button:hover { background: #1e3a8a; }
    .timestamp { color: #6b7280; font-size: 11px; font-family: monospace; }
    .error-text { color: #dc2626; font-size: 12px; }
    .loading { text-align: center; padding: 40px; color: #6b7280; }
    .chart-bar { display: inline-block; background: linear-gradient(135deg, #facc15 0%, #ef4444 100%); height: 24px; vertical-align: middle; border-radius: 4px; min-width: 4px; }
    .footer { text-align: center; padding: 24px; color: #9ca3af; font-size: 12px; }
    .pulse {
      display: inline-block; width: 8px; height: 8px; border-radius: 50%;
      background: #16a34a; margin-right: 6px; animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0% { box-shadow: 0 0 0 0 rgba(22,163,74,0.7); }
      70% { box-shadow: 0 0 0 8px rgba(22,163,74,0); }
      100% { box-shadow: 0 0 0 0 rgba(22,163,74,0); }
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>⚡ AhmedETAP — Email Dashboard</h1>
    <div class="sub">Real-time monitoring of transactional email delivery via Resend</div>
  </div>

  <div class="container">
    <div class="controls">
      <label>Window:
        <select id="windowHours" onchange="reloadStats()">
          <option value="1">Last hour</option>
          <option value="6">Last 6 hours</option>
          <option value="24" selected>Last 24 hours</option>
          <option value="168">Last 7 days</option>
          <option value="720">Last 30 days</option>
        </select>
      </label>
      <label>Auto-refresh:
        <select id="refreshInterval" onchange="setRefresh()">
          <option value="0">Off</option>
          <option value="10">10s</option>
          <option value="30" selected>30s</option>
          <option value="60">60s</option>
        </select>
      </label>
      <button onclick="reloadStats()">Reload</button>
      <span style="margin-left:auto; color:#6b7280; font-size:12px;">
        <span class="pulse"></span>
        Live · <span id="lastUpdate">—</span>
      </span>
    </div>

    <div class="grid grid-4" style="margin-bottom: 16px;">
      <div class="card stat-card">
        <div class="label">Total Sends</div>
        <div class="value" id="stat-total">—</div>
        <div class="sub" id="stat-window-label">last 24h</div>
      </div>
      <div class="card stat-card success">
        <div class="label">Success Rate</div>
        <div class="value" id="stat-success-rate">—</div>
        <div class="sub" id="stat-success-detail">— succeeded</div>
      </div>
      <div class="card stat-card danger">
        <div class="label">Failures</div>
        <div class="value" id="stat-failed">—</div>
        <div class="sub" id="stat-failed-detail">—</div>
      </div>
      <div class="card stat-card warning">
        <div class="label">Avg Latency</div>
        <div class="value" id="stat-latency">—</div>
        <div class="sub">milliseconds</div>
      </div>
    </div>

    <div class="grid grid-2" style="margin-bottom: 16px;">
      <div class="card">
        <h3>📊 Sends by Day (last 7 days)</h3>
        <div id="byDayChart" style="min-height: 200px;"></div>
      </div>
      <div class="card">
        <h3>🎯 Sends by Flow</h3>
        <div id="byFlow" style="min-height: 200px;"></div>
      </div>
    </div>

    <div class="card" style="margin-bottom: 16px;">
      <h3>⚠️ Top Errors</h3>
      <div id="topErrors"></div>
    </div>

    <div class="card">
      <h3>📋 Recent Sends</h3>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Recipient</th>
            <th>Subject</th>
            <th>Flow</th>
            <th>Status</th>
            <th>Ms</th>
            <th>Message ID</th>
          </tr>
        </thead>
        <tbody id="recentTable">
          <tr><td colspan="7" class="loading">Loading...</td></tr>
        </tbody>
      </table>
    </div>

    <div class="footer">
      © 2026 AhmedETAP · Email monitoring dashboard ·
      <a href="/docs" style="color: #6b7280;">API docs</a> ·
      <a href="/api/v1/email-dashboard/api/config" style="color: #6b7280;">Config</a>
    </div>
  </div>

  <script>
    const API_BASE = '/api/v1/email-dashboard/api';
    let refreshTimer = null;

    async function fetchJSON(url) {
      const resp = await fetch(url);
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      return resp.json();
    }

    async function reloadStats() {
      const windowHours = document.getElementById('windowHours').value;
      document.getElementById('stat-window-label').textContent = 'last ' + windowHours + 'h';

      try {
        const [statsResp, recentResp, byDayResp] = await Promise.all([
          fetchJSON(`${API_BASE}/stats?window_hours=${windowHours}`),
          fetchJSON(`${API_BASE}/recent?limit=100`),
          fetchJSON(`${API_BASE}/by-day?days=7`),
        ]);

        const stats = statsResp.stats || {};
        document.getElementById('stat-total').textContent = stats.total || 0;
        document.getElementById('stat-success-rate').textContent = (stats.success_rate || 0) + '%';
        document.getElementById('stat-success-detail').textContent = (stats.succeeded || 0) + ' succeeded';
        document.getElementById('stat-failed').textContent = stats.failed || 0;
        document.getElementById('stat-failed-detail').textContent = (stats.by_flow ? Object.values(stats.by_flow).reduce((a,b)=>a+(b.failed||0),0) : 0) + ' failed across flows';
        document.getElementById('stat-latency').textContent = stats.avg_elapsed_ms || 0;

        // By-day chart
        const days = byDayResp.days || [];
        const maxCount = Math.max(...days.map(d => d.total || 0), 1);
        document.getElementById('byDayChart').innerHTML = days.map(d => `
          <div style="margin-bottom: 8px;">
            <div style="font-size: 11px; color: #6b7280; margin-bottom: 2px;">${d.date}</div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <div class="chart-bar" style="width: ${((d.total / maxCount) * 100)}%; min-width: 4px;"></div>
              <span style="font-size: 12px; font-weight: 600;">${d.total}</span>
              <span style="font-size: 11px; color: #16a34a;">✓${d.succeeded||0}</span>
              <span style="font-size: 11px; color: #dc2626;">✗${d.failed||0}</span>
            </div>
          </div>
        `).join('');

        // By-flow breakdown
        const flows = stats.by_flow || {};
        const flowEntries = Object.entries(flows).sort((a,b) => (b[1].total||0) - (a[1].total||0));
        document.getElementById('byFlow').innerHTML = flowEntries.length === 0
          ? '<div style="color:#9ca3af; text-align:center; padding:40px;">No flows yet</div>'
          : '<table><tbody>' + flowEntries.map(([flow, s]) => `
              <tr>
                <td><span class="badge badge-flow">${flow}</span></td>
                <td style="text-align:right; font-weight:600;">${s.total||0}</td>
                <td style="text-align:right; color:#16a34a;">✓ ${s.success||0}</td>
                <td style="text-align:right; color:#dc2626;">✗ ${s.failed||0}</td>
              </tr>`).join('') + '</tbody></table>';

        // Top errors
        const errors = stats.top_errors || [];
        document.getElementById('topErrors').innerHTML = errors.length === 0
          ? '<div style="color:#9ca3af; text-align:center; padding:20px;">🎉 No errors in window</div>'
          : '<table><thead><tr><th>Error</th><th style="text-align:right;">Count</th></tr></thead><tbody>'
              + errors.map(e => `<tr><td class="error-text">${e.error}</td><td style="text-align:right; font-weight:600;">${e.count}</td></tr>`).join('')
              + '</tbody></table>';

        // Recent table
        const records = recentResp.records || [];
        document.getElementById('recentTable').innerHTML = records.length === 0
          ? '<tr><td colspan="7" class="loading">No records yet</td></tr>'
          : records.slice(0, 50).map(r => `
              <tr>
                <td class="timestamp">${(r.timestamp||'').slice(0,19).replace('T',' ')}</td>
                <td>${escapeHtml(r.recipient||'')}</td>
                <td style="max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(r.subject||'')}">${escapeHtml(r.subject||'')}</td>
                <td><span class="badge badge-flow">${r.flow||'—'}</span></td>
                <td>${r.success ? '<span class="badge badge-success">OK</span>' : '<span class="badge badge-failed">FAIL</span>'}</td>
                <td style="text-align:right;">${r.elapsed_ms||0}</td>
                <td class="timestamp" title="${escapeHtml(r.message_id||'')}">${(r.message_id||'').slice(0,12)}</td>
              </tr>`).join('');

        document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
      } catch (err) {
        console.error('Reload failed:', err);
        document.getElementById('recentTable').innerHTML = `<tr><td colspan="7" class="loading" style="color:#dc2626;">Error: ${escapeHtml(err.message)}</td></tr>`;
      }
    }

    function setRefresh() {
      if (refreshTimer) clearInterval(refreshTimer);
      const interval = parseInt(document.getElementById('refreshInterval').value);
      if (interval > 0) {
        refreshTimer = setInterval(reloadStats, interval * 1000);
      }
    }

    function escapeHtml(s) {
      return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }

    // Initial load
    reloadStats();
    setRefresh();
  </script>
</body>
</html>"""


@router.get("/", response_class=HTMLResponse, summary="Email dashboard HTML page")
async def dashboard_page(request: Request) -> HTMLResponse:
    """Serve the email monitoring dashboard HTML page.

    The HTML page itself is public (no sensitive data — just a shell).
    Authentication is enforced on the JavaScript API calls that load data.
    """
    # Public HTML page — auth enforced on JS API calls
    return HTMLResponse(content=_DASHBOARD_HTML)


__all__ = ["router"]
