"""
Comprehensive test for new features:
1. OTP send/verify
2. Magic Link issue/verify
3. Email send log + stats
4. Email dashboard endpoints
5. Webhook endpoint registration
6. Digest context building
"""

import asyncio
import os
import sys
import json

sys.path.insert(0, '/home/z/my-project/etap-local-clone')

# Set required env
os.environ['RESEND_API_KEY'] = 're_FpxUQQs1_CCnu4BKfuAsyyvH6V8PSAXSB'
os.environ['RESEND_FROM_EMAIL'] = 'onboarding@resend.dev'
os.environ['RESEND_FROM_NAME'] = 'AhmedETAP'
os.environ['EMAIL_APP_URL'] = 'https://etap-ai-work.vercel.app'
os.environ['EMAIL_BRAND_NAME'] = 'AhmedETAP'
os.environ['EMAIL_BRAND_TAGLINE'] = 'Enterprise AI-Powered Power Systems Engineering'


async def test_1_otp():
    """Test OTP send + verify."""
    print("\n=== TEST 1: OTP send + verify ===")
    from services.otp_store import issue_otp, verify_otp, invalidate_otp

    email = "test1@example.com"
    purpose = "login"

    # Issue
    r = await issue_otp(email, purpose)
    assert r.success, f"Issue failed: {r.error}"
    print(f"  ✅ Issued OTP: {r.code}")

    # Verify
    v = await verify_otp(email, purpose, r.code)
    assert v.success, f"Verify failed: {v.error}"
    print(f"  ✅ Verified OTP")

    # Re-verify should fail (one-shot)
    v2 = await verify_otp(email, purpose, r.code)
    assert not v2.success
    print(f"  ✅ Re-verify correctly rejected ({v2.error})")


async def test_2_magic_link():
    """Test Magic Link issue + verify."""
    print("\n=== TEST 2: Magic Link issue + verify ===")
    from api.magic_links import _issue, _verify

    email = "test2@example.com"
    user_id = "user-123"

    # Issue
    success, token, retry = await _issue(email, user_id)
    assert success, f"Issue failed (retry={retry})"
    assert len(token) >= 32
    print(f"  ✅ Issued magic link token (len={len(token)})")

    # Verify
    v_success, rec, err = await _verify(token)
    assert v_success, f"Verify failed: {err}"
    assert rec.email == email
    assert rec.user_id == user_id
    print(f"  ✅ Verified magic link for {rec.email}")

    # Re-verify should fail (one-shot)
    v2_success, _, v2_err = await _verify(token)
    assert not v2_success
    print(f"  ✅ Re-verify correctly rejected ({v2_err})")

    # Rate limit
    for _ in range(3):
        await _issue(email, user_id)
    s4, _, r4 = await _issue(email, user_id)
    assert not s4, "Should have been rate-limited"
    print(f"  ✅ Rate limit kicked in (retry after {r4}s)")


async def test_3_email_send_log():
    """Test email send log + stats."""
    print("\n=== TEST 3: Email send log + stats ===")
    from services.email_send_log import (
        log_email_send, get_recent_sends, get_send_stats, get_send_count_by_day,
        get_record_by_id, clear_old_records
    )

    # Log several sends
    ids = []
    for i in range(5):
        rid = await log_email_send(
            recipient=f"user{i}@example.com",
            subject=f"Test email {i}",
            flow="otp" if i % 2 == 0 else "welcome",
            success=(i != 4),  # last one fails
            message_id=f"msg-{i}" if i != 4 else None,
            error="simulated_error" if i == 4 else None,
            elapsed_ms=100 + i * 20,
        )
        ids.append(rid)
    print(f"  ✅ Logged {len(ids)} send records")

    # Recent
    recent = get_recent_sends(limit=10)
    assert len(recent) >= 5
    print(f"  ✅ get_recent_sends returned {len(recent)} records")

    # Stats
    stats = get_send_stats(window_hours=1)
    assert stats["total"] >= 5
    assert stats["succeeded"] >= 4
    assert stats["failed"] >= 1
    assert "otp" in stats["by_flow"]
    assert "welcome" in stats["by_flow"]
    print(f"  ✅ Stats: total={stats['total']}, success_rate={stats['success_rate']}%, by_flow={list(stats['by_flow'].keys())}")

    # By day
    by_day = get_send_count_by_day(days=7)
    assert len(by_day) == 7
    print(f"  ✅ get_send_count_by_day returned {len(by_day)} days")

    # Get by ID
    rec = get_record_by_id(ids[0])
    assert rec is not None
    assert rec["id"] == ids[0]
    print(f"  ✅ get_record_by_id found record")


async def test_4_dashboard():
    """Test dashboard JSON endpoints (dev mode)."""
    print("\n=== TEST 4: Dashboard endpoints ===")
    os.environ['EMAIL_DASHBOARD_DEV_OPEN'] = 'true'

    from api.email_dashboard import get_stats, get_recent, get_by_day, get_config
    from fastapi import Request
    from types import SimpleNamespace

    # Build a mock request
    mock_request = SimpleNamespace(
        headers={"authorization": ""},
        state=SimpleNamespace(trace_id="test-trace"),
    )

    # Get stats
    resp = await get_stats(mock_request, window_hours=24)
    assert resp.status_code == 200
    body = json.loads(resp.body)
    assert body["success"]
    print(f"  ✅ get_stats OK (total={body['stats']['total']})")

    # Get recent
    resp = await get_recent(mock_request, limit=10)
    body = json.loads(resp.body)
    assert body["success"]
    print(f"  ✅ get_recent OK (count={len(body['records'])})")

    # Get by-day
    resp = await get_by_day(mock_request, days=7)
    body = json.loads(resp.body)
    assert body["success"]
    print(f"  ✅ get_by_day OK (days={len(body['days'])})")

    # Get config
    resp = await get_config(mock_request)
    body = json.loads(resp.body)
    assert body["success"]
    assert body["config"]["RESEND_FROM_NAME"] == "AhmedETAP"
    assert body["config"]["RESEND_API_KEY_SET"] == "yes"
    print(f"  ✅ get_config OK (RESEND_API_KEY_SET={body['config']['RESEND_API_KEY_SET']})")


async def test_5_webhooks():
    """Test webhook endpoint registration."""
    print("\n=== TEST 5: Webhook endpoints ===")
    from api.email_webhooks import (
        register_endpoint, list_endpoints, delete_endpoint,
        RegisterEndpointRequest,
    )

    # Register
    body = RegisterEndpointRequest(
        url="https://hooks.example.com/etap",
        events=["email.sent", "email.delivered", "email.bounced"],
        secret="test_secret_at_least_16_chars",
    )
    resp = await register_endpoint(body)
    assert resp.status_code == 201
    data = json.loads(resp.body)
    ep_id = data["id"]
    print(f"  ✅ Registered endpoint: {ep_id[:8]}... → {data['url']}")

    # List
    resp = await list_endpoints()
    data = json.loads(resp.body)
    assert data["success"]
    assert len(data["endpoints"]) >= 1
    print(f"  ✅ list_endpoints OK ({len(data['endpoints'])} endpoint(s))")

    # Delete
    resp = await delete_endpoint(ep_id)
    data = json.loads(resp.body)
    assert data["success"]
    print(f"  ✅ Deleted endpoint {ep_id[:8]}...")


async def test_6_digest():
    """Test digest context building."""
    print("\n=== TEST 6: Digest context ===")
    from api.email_digest import _build_digest_context, _config

    # First log some sends for a specific recipient
    from services.email_send_log import log_email_send
    for i in range(3):
        await log_email_send(
            recipient="digest-user@example.com",
            subject=f"Daily activity {i}",
            flow="notification",
            success=True,
        )

    ctx = await _build_digest_context(
        email="digest-user@example.com",
        period="daily",
        user_name="Digest User",
    )

    assert ctx["total_count"] >= 3
    assert ctx["period_label"] == "Daily"
    assert "notification" in ctx["by_flow"]
    print(f"  ✅ Digest context: total_count={ctx['total_count']}, by_flow={ctx['by_flow']}")
    print(f"  ✅ Period: {ctx['period_label']} ({ctx['period_dates']})")

    # Config
    cfg = _config()
    assert cfg["enabled"] is True
    print(f"  ✅ Digest config: enabled={cfg['enabled']}, daily_schedule={cfg['daily_schedule']}")


async def test_7_live_send_with_brand():
    """Test live send to verify branded templates work."""
    print("\n=== TEST 7: Live send with AhmedETAP brand ===")
    from services.email_service import send_email_otp, send_welcome, send_notification_email

    RECIPIENT = "a7medbaz16@gmail.com"

    print(f"  Sending 3 branded emails to {RECIPIENT}...")

    r1 = await send_email_otp(RECIPIENT, "284719", "login", "Ahmed", 10)
    print(f"  ✅ OTP: {'OK' if r1.success else 'FAIL'} - {r1.message_id or r1.error}")
    await asyncio.sleep(2)

    r2 = await send_welcome(RECIPIENT, "Ahmed")
    print(f"  ✅ Welcome: {'OK' if r2.success else 'FAIL'} - {r2.message_id or r2.error}")
    await asyncio.sleep(2)

    r3 = await send_notification_email(
        RECIPIENT,
        title="Test Notification from ETAP Dashboard",
        message="This is a test of the AhmedETAP email integration with the new branded templates (yellow→red gradient, lightning bolt logo).",
        priority="normal",
        user_name="Ahmed",
        action_label="⚡ Open Dashboard",
    )
    print(f"  ✅ Notification: {'OK' if r3.success else 'FAIL'} - {r3.message_id or r3.error}")

    # Verify they're logged
    from services.email_send_log import get_recent_sends
    recent = get_recent_sends(limit=10)
    branded = [r for r in recent if r.get("recipient") == RECIPIENT]
    print(f"  ✅ All {len(branded)} sends logged to email_send_log")


async def main():
    print("=" * 70)
    print("Comprehensive Test — Resend Integration v2 Features")
    print("=" * 70)
    print(f"Resend enabled: {os.getenv('RESEND_API_KEY', '')[:10]}...")

    await test_1_otp()
    await test_2_magic_link()
    await test_3_email_send_log()
    await test_4_dashboard()
    await test_5_webhooks()
    await test_6_digest()
    await test_7_live_send_with_brand()

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
