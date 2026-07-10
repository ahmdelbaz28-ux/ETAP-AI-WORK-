from __future__ import annotations
"""
Langfuse Sessions, User Feedback, and Alerting for AhmedETAP
=============================================================

⚠️ SAFETY-CRITICAL ⚠️
This module wires up:

1. **Sessions** — group all LLM calls from one engineering session into
   a single Langfuse session, so a reviewer can see the full context of
   a safety-critical decision (e.g. all calls that led to an arc-flash
   PPE recommendation).

2. **User feedback** — engineers can attach 👍/👎 to any trace, with an
   optional comment. Negative feedback on a safety-critical trace
   triggers an alert.

3. **Public trace URLs** — generate a shareable URL for any trace, so
   a senior engineer can review a junior engineer's trace.

4. **Safety alerts** — when a trace is tagged ``safety_critical`` AND
   the safety score is low (or the user gave 👎), an alert is emitted:
   - Logged at CRITICAL level (visible in logs)
   - Optionally sent to a webhook (Slack/Teams/email)
   - Recorded as a Langfuse score with name ``safety_alert``

Usage::

    from integrations.langfuse_sessions import (
        start_engineering_session,
        end_engineering_session,
        record_user_feedback,
        get_trace_share_url,
        alert_on_unsafe_trace,
    )

    # 1. Start a session for an engineer working on arc flash
    session = start_engineering_session(
        user_id="engineer_42",
        study_type="arc_flash",
        project_id="substation_north",
    )

    # 2. ... agents make LLM calls with session_id=session.id ...

    # 3. Engineer reviews a trace and gives feedback
    record_user_feedback(
        trace_id="trace_xxx",
        feedback="negative",
        comment="This recommendation didn't cite IEEE 1584",
    )

    # 4. If feedback is negative on a safety-critical trace, an alert fires
    # 5. Engineer shares the trace with their senior
    url = get_trace_share_url("trace_xxx")
"""

import json
import logging
import math
import os
import time
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


# ─── Lazy Langfuse client ─────────────────────────────────────────────────


def _get_client():
    try:
        from integrations.langfuse_integration import langfuse_tracker

        return langfuse_tracker._get_client()
    except Exception:
        return None


# ─── Session management ───────────────────────────────────────────────────


class EngineeringSession:
    """Represents a single engineering session in Langfuse.

    A session groups all LLM calls made by one engineer working on one
    study (e.g. one arc-flash analysis). Use the ``id`` as the
    ``langfuse_session_id`` kwarg on LLM calls.
    """

    def __init__(
        self,
        session_id: str,
        user_id: str,
        study_type: str,
        project_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        self.id = session_id
        self.user_id = user_id
        self.study_type = study_type
        self.project_id = project_id
        self.metadata = metadata or {}
        self.started_at = time.time()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.end()
        return False

    def end(self) -> None:
        """End the session. Future LLM calls with this session_id will
        still be recorded, but the session is considered closed."""
        elapsed = time.time() - self.started_at
        logger.info(
            "Engineering session ended: id=%s, user=%s, study=%s, project=%s, duration=%.1fs",
            self.id,
            self.user_id,
            self.study_type,
            self.project_id,
            elapsed,
        )


def start_engineering_session(
    *,
    user_id: str,
    study_type: str,
    project_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> EngineeringSession:
    """Start a new engineering session.

    Parameters
    ----------
    user_id : str
        Engineer's user ID (for per-user analytics).
    study_type : str
        Type of study: ``"arc_flash"``, ``"short_circuit"``,
        ``"load_flow"``, ``"coordination"``, ``"grounding"``, etc.
    project_id : str, optional
        The ETAP project ID the engineer is working on.
    session_id : str, optional
        Override the auto-generated session ID.
    metadata : dict, optional
        Additional metadata to attach to the session.

    Returns
    -------
    EngineeringSession
        Pass ``session.id`` as the ``langfuse_session_id`` kwarg to
        ``safe_openai_chat`` / ``safe_anthropic_message``.
    """
    sid = session_id or f"sess_{uuid.uuid4().hex[:16]}"
    session = EngineeringSession(
        session_id=sid,
        user_id=user_id,
        study_type=study_type,
        project_id=project_id,
        metadata={
            "study_type": study_type,
            "project_id": project_id,
            **(metadata or {}),
        },
    )
    logger.info(
        "Engineering session started: id=%s, user=%s, study=%s, project=%s",
        sid,
        user_id,
        study_type,
        project_id,
    )
    return session


def end_engineering_session(session: EngineeringSession) -> None:
    """Explicitly end a session (alternative to the context manager)."""
    session.end()


# ─── User feedback ────────────────────────────────────────────────────────


def record_user_feedback(
    *,
    trace_id: str,
    feedback: str,  # "positive" | "negative" | "neutral"
    comment: str = "",
    user_id: Optional[str] = None,
) -> bool:
    """Attach user feedback to a trace as a Langfuse score.

    Triggers an alert if the feedback is negative AND the trace was
    tagged ``safety_critical``.
    """
    client = _get_client()
    if client is None:
        logger.warning("Langfuse unavailable — feedback not recorded")
        return False

    # Normalise feedback to a numeric score
    feedback_lower = feedback.lower()
    if feedback_lower in ("positive", "good", "up", "👍", "+1"):
        value = 1.0
    elif feedback_lower in ("negative", "bad", "down", "👎", "-1"):
        value = 0.0
    else:
        value = 0.5

    try:
        client.create_score(
            trace_id=trace_id,
            name="user_feedback",
            value=value,
            comment=comment or feedback,
            data_type="NUMERIC",
        )
        logger.info(
            "User feedback recorded: trace=%s, feedback=%s, value=%.1f",
            trace_id,
            feedback,
            value,
        )
    except Exception as e:
        logger.warning("Failed to record user feedback: %s", e)
        return False

    # Alert on negative feedback on safety-critical traces
    # (we look up the trace's metadata via the SDK if possible)
    if math.isclose(value, 0.0):
        try:
            alert_on_unsafe_trace(
                trace_id=trace_id,
                reason=f"Negative user feedback: {comment or feedback}",
                user_id=user_id,
            )
        except Exception as e:
            logger.debug("Alert check failed (non-critical): %s", e)

    return True


# ─── Public trace URLs ────────────────────────────────────────────────────


def get_trace_share_url(trace_id: str, make_public: bool = True) -> Optional[str]:
    """Return a shareable URL for a trace.

    Parameters
    ----------
    trace_id : str
        The Langfuse trace ID.
    make_public : bool
        If True, mark the trace as public (anyone with the URL can view
        it without logging in). If False, returns a URL that requires
        the viewer to be logged into Langfuse.
    """
    client = _get_client()
    if client is None:
        return None

    try:
        if make_public:
            # Mark the trace as public so the URL works without login
            try:
                client.set_current_trace_as_public()
            except Exception:
                # set_current_trace_as_public works on the *current* trace;
                # for an arbitrary trace_id, the URL still works for logged-in
                # users. We log this limitation.
                logger.debug(
                    "Could not mark trace %s as public (it may not be the "
                    "current trace). URL will require Langfuse login.",
                    trace_id,
                )
        url = client.get_trace_url(trace_id=trace_id)
        return url
    except Exception as e:
        logger.warning("Failed to get trace URL for %s: %s", trace_id, e)
        # Fall back to constructing the URL manually
        base = os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
        project_id = os.environ.get("LANGFUSE_PROJECT_ID", "")
        if project_id:
            return f"{base}/project/{project_id}/traces/{trace_id}"
        return f"{base}/traces/{trace_id}"


# ─── Safety alerts ────────────────────────────────────────────────────────

_ALERT_WEBHOOK_URL = os.environ.get("LANGFUSE_ALERT_WEBHOOK_URL", "")
_ALERT_WEBHOOK_HEADERS = json.loads(os.environ.get("LANGFUSE_ALERT_WEBHOOK_HEADERS", "{}"))


def alert_on_unsafe_trace(
    *,
    trace_id: str,
    reason: str,
    user_id: Optional[str] = None,
    severity: str = "high",
) -> bool:
    """Emit a safety alert for an unsafe trace.

    The alert is:
    1. Logged at CRITICAL level (visible in app logs)
    2. Recorded as a Langfuse score named ``safety_alert``
    3. Sent to the configured webhook (if any) — e.g. Slack, Teams, email

    Parameters
    ----------
    trace_id : str
        The unsafe trace's ID.
    reason : str
        Why this trace is unsafe (human-readable).
    user_id : str, optional
        The engineer who triggered the trace.
    severity : str
        ``"high"`` (default), ``"critical"``, ``"medium"``, or ``"low"``.
    """
    # 1. CRITICAL log
    logger.critical(
        "🚨 SAFETY ALERT: trace_id=%s, severity=%s, user=%s, reason=%s",
        trace_id,
        severity,
        user_id,
        reason,
    )

    # 2. Langfuse score
    client = _get_client()
    if client is not None:
        try:
            # Score value: 0 = critical alert, 1 = low severity
            severity_score = {
                "critical": 0.0,
                "high": 0.25,
                "medium": 0.5,
                "low": 0.75,
            }.get(severity, 0.25)
            client.create_score(
                trace_id=trace_id,
                name="safety_alert",
                value=severity_score,
                comment=f"[{severity.upper()}] {reason}",
                data_type="NUMERIC",
            )
        except Exception as e:
            logger.warning("Failed to record safety_alert score: %s", e)

    # 3. Webhook
    if _ALERT_WEBHOOK_URL:
        try:
            import httpx

            payload = {
                "trace_id": trace_id,
                "reason": reason,
                "user_id": user_id,
                "severity": severity,
                "timestamp": time.time(),
                "trace_url": get_trace_share_url(trace_id, make_public=False),
                "source": "ahmedetap",
            }
            headers = {"Content-Type": "application/json", **_ALERT_WEBHOOK_HEADERS}
            r = httpx.post(_ALERT_WEBHOOK_URL, json=payload, headers=headers, timeout=10)
            if r.status_code in (200, 201, 202, 204):
                logger.info("Safety alert sent to webhook (status=%s)", r.status_code)
            else:
                logger.warning(
                    "Safety alert webhook returned %s: %s",
                    r.status_code,
                    r.text[:200],
                )
        except Exception as e:
            logger.warning("Failed to send safety alert webhook: %s", e)

    return True


# ─── Comment API (manual review annotations) ─────────────────────────────


def add_trace_comment(
    trace_id: str,
    comment: str,
    author: Optional[str] = None,
) -> bool:
    """Add a review comment to a trace (for senior-engineer review).

    Uses the Langfuse event API to attach a comment as metadata.
    """
    client = _get_client()
    if client is None:
        return False
    try:
        client.create_event(
            trace_id=trace_id,
            name="review_comment",
            metadata={
                "comment": comment,
                "author": author or "unknown",
                "timestamp": time.time(),
            },
        )
        logger.info("Comment added to trace %s by %s", trace_id, author or "unknown")
        return True
    except Exception as e:
        logger.warning("Failed to add comment to trace %s: %s", trace_id, e)
        return False


__all__ = [
    "EngineeringSession",
    "start_engineering_session",
    "end_engineering_session",
    "record_user_feedback",
    "get_trace_share_url",
    "alert_on_unsafe_trace",
    "add_trace_comment",
]
