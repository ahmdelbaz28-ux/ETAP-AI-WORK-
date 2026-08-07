"""
Security Middleware Wiring
==========================
يسجِّل RASP + ABAC middleware على FastAPI app.

الـ RASP و ABAC موجودان في security/rasp.py + security/abac.py (1,110 LOC)
لكن **غير مسجَّلين** على الـ FastAPI app — أي أنهم dead code.

هذا الـ module يوفر:
  - install_security_middleware(app): يسجِّل كل middleware الأمني
  - verify_security_wiring(app): يتحقق من التسجيل
  - RASPMiddleware: wrapper حول RASPEngine يعمل كـ Starlette middleware

Branch: fix/security-wiring-rasp-abac
Refs: PRODUCTION_PLAN/01_SELF_CRITICISM.md §3.6 #23-24
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)


# ─── RASP Middleware (wrapper around RASPEngine) ──────────────────


try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response

    _HAS_STARLETTE = True
except ImportError:
    _HAS_STARLETTE = False
    BaseHTTPMiddleware = None  # type: ignore[assignment,misc]
    Request = None  # type: ignore[assignment,misc]
    JSONResponse = None  # type: ignore[assignment,misc]
    Response = None  # type: ignore[assignment,misc]


if _HAS_STARLETTE:

    class RASPMiddleware(BaseHTTPMiddleware):
        """FastAPI/Starlette middleware for RASP attack detection.

        Wraps the RASPEngine from security/rasp.py. Inspects incoming
        request data (query params, body, path, headers) against attack
        detection rules. Blocks requests that match BLOCK-action rules.

        Parameters
        ----------
        app : ASGI app
            The FastAPI/Starlette application.
        engine : RASPEngine, optional
            Pre-configured RASP engine. If not provided, creates one
            with default rules via create_default_rasp_engine().
        public_paths : list[str], optional
            Path prefixes that bypass RASP checks (default: health/docs).
        """

        def __init__(
            self,
            app: Any,
            engine: Any | None = None,
            public_paths: list[str] | None = None,
        ) -> None:
            super().__init__(app)
            if engine is None:
                try:
                    from security.rasp import create_default_rasp_engine
                    engine = create_default_rasp_engine()
                except ImportError as exc:
                    logger.error("Failed to import RASPEngine: %s", exc)
                    engine = None
            self.engine = engine
            self._public_paths = public_paths or [
                "/health",
                "/health/deep",
                "/ready",
                "/docs",
                "/redoc",
                "/openapi.json",
                "/metrics",
                "/prometheus",
            ]

        async def dispatch(self, request: Request, call_next: Any) -> Any:
            """Inspect request + block if attack detected."""
            if self.engine is None or not self.engine.enabled:
                return await call_next(request)

            # Skip public paths
            path = request.url.path
            if any(path.startswith(p) for p in self._public_paths):
                return await call_next(request)

            # Build inspection data
            inspect_data: dict[str, Any] = {
                "path": path,
                "query": dict(request.query_params),
                "headers": {k: v for k, v in request.headers.items()},
            }

            # Read body (for POST/PUT/PATCH)
            if request.method in ("POST", "PUT", "PATCH"):
                try:
                    body_bytes = await request.body()
                    if body_bytes:
                        try:
                            inspect_data["body"] = json.loads(body_bytes)
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            inspect_data["body"] = body_bytes.decode(
                                "utf-8", errors="replace"
                            )
                except Exception:
                    pass  # body already consumed or unavailable

            # Inspect
            results = self.engine.inspect(inspect_data)

            # Check for BLOCK actions
            for result in results:
                if result.action.value == "block":
                    logger.warning(
                        "RASP BLOCKED request: rule=%s severity=%s "
                        "field=%s path=%s method=%s",
                        result.rule_name,
                        result.severity.value,
                        result.matched_field,
                        path,
                        request.method,
                    )
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "Request blocked by security policy",
                            "rule": result.rule_name,
                            "severity": result.severity.value,
                            "trace_id": getattr(request.state, "trace_id", ""),
                        },
                    )

            # Log non-blocked detections
            for result in results:
                if result.action.value == "log":
                    logger.info(
                        "RASP LOGGED: rule=%s field=%s path=%s",
                        result.rule_name, result.matched_field, path,
                    )

            return await call_next(request)


# ─── Install Function ─────────────────────────────────────────────


def install_security_middleware(app: Any) -> None:
    """
    تسجيل كل middleware الأمني على FastAPI app.

    Middleware المسجَّلة (بالترتيب من outer إلى inner):
        1. RASPMiddleware — Runtime Application Self-Protection
        2. ABACMiddleware — Attribute-Based Access Control
        3. BodySizeLimitMiddleware — (already registered in api/routes.py)
        4. CORSMiddleware — (already registered in api/routes.py)

    Environment variables:
        RASP_ENABLED: "true" (default) — تفعيل RASP
        ABAC_ENABLED: "true" (default) — تفعيل ABAC
    """
    rasp_enabled = os.environ.get("RASP_ENABLED", "true").lower() == "true"
    abac_enabled = os.environ.get("ABAC_ENABLED", "true").lower() == "true"

    # ─── 1. RASP Middleware ───────────────────────────────────────
    if rasp_enabled and _HAS_STARLETTE:
        try:
            app.add_middleware(RASPMiddleware)
            logger.info("✅ RASPMiddleware registered")
        except Exception as exc:
            logger.error("❌ Failed to register RASPMiddleware: %s", exc)
            if os.environ.get("ENVIRONMENT") == "production":
                raise RuntimeError(
                    f"RASP middleware registration failed in production: {exc}"
                ) from exc

    # ─── 2. ABAC Middleware ──────────────────────────────────────
    if abac_enabled and _HAS_STARLETTE:
        try:
            from security.abac import ABACMiddleware  # type: ignore

            app.add_middleware(ABACMiddleware)
            logger.info("✅ ABACMiddleware registered")
        except ImportError as exc:
            logger.error("❌ ABACMiddleware not available: %s", exc)
            if os.environ.get("ENVIRONMENT") == "production":
                raise RuntimeError(
                    f"ABAC middleware not available in production: {exc}"
                ) from exc
        except Exception as exc:
            logger.error("❌ Failed to register ABACMiddleware: %s", exc)
            if os.environ.get("ENVIRONMENT") == "production":
                raise

    # ─── Summary ─────────────────────────────────────────────────
    middleware_names = [m.cls.__name__ for m in app.user_middleware]
    logger.info("🛡️ Total middleware registered: %d", len(middleware_names))

    # Verify required middleware in production
    if os.environ.get("ENVIRONMENT") == "production":
        required = []
        if rasp_enabled:
            required.append("RASPMiddleware")
        if abac_enabled:
            required.append("ABACMiddleware")

        for req in required:
            if req not in middleware_names:
                raise RuntimeError(
                    f"Required middleware {req} is not registered in production. "
                    f"Registered: {middleware_names}"
                )

        logger.info("✅ All required production middleware verified")


def verify_security_wiring(app: Any) -> dict[str, Any]:
    """
    التحقق من أن كل middleware الأمني مسجَّل.

    Returns:
        dict mapping middleware name → is_registered + total count.
    """
    middleware_names = [m.cls.__name__ for m in app.user_middleware]

    return {
        "RASPMiddleware": "RASPMiddleware" in middleware_names,
        "ABACMiddleware": "ABACMiddleware" in middleware_names,
        "BodySizeLimitMiddleware": any(
            "BodySize" in name for name in middleware_names
        ),
        "CORSMiddleware": "CORSMiddleware" in middleware_names,
        "total_count": len(middleware_names),
        "all_names": middleware_names,
    }


__all__ = [
    "install_security_middleware",
    "verify_security_wiring",
    "RASPMiddleware",
]
