"""
Attribute-Based Access Control (ABAC) for AhmedETAP Platform
============================================================
Extends the existing RBAC system with fine-grained, attribute-driven policies.

Features:
- Policy engine evaluating Subject + Action + Resource + Environment → Allow/Deny
- Composable rule types: role, attribute, resource, time, IP
- Default-deny posture (explicit allow required)
- FastAPI middleware for automatic ABAC enforcement on every request
- Policy hot-reload and priority ordering

Policy Rule Types
-----------------
- Role rules      : ``role == "engineer"``
- Attribute rules : ``department == "power_systems" AND region == "MENA"``
- Resource rules  : ``resource.clearance_level <= subject.clearance_level``
- Time rules      : ``environment.time.hour >= 8 AND environment.time.hour <= 18``
- IP rules        : ``environment.ip in allowed_ranges``
"""

from __future__ import annotations

import ipaddress
import logging
import operator
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any

from compat import StrEnum

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Operator mapping for declarative rule conditions
# ---------------------------------------------------------------------------

_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "in": lambda val, container: val in container,
    "not_in": lambda val, container: val not in container,
    "contains": lambda container, val: val in container,
    "matches": lambda val, pattern: bool(re.search(pattern, str(val))),
}


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------


class RuleType(StrEnum):
    """Supported ABAC rule types."""

    ROLE = "role"
    ATTRIBUTE = "attribute"
    RESOURCE = "resource"
    TIME = "time"
    IP = "ip"


@dataclass
class ABACRule:
    """A single ABAC rule.

    Parameters
    ----------
    rule_type : RuleType
        Category of the rule (role, attribute, resource, time, ip).
    field_path : str
        Dot-separated path to the attribute on the relevant context
        (e.g. ``"role"``, ``"department"``, ``"resource.clearance_level"``).
    operator : str
        Comparison operator string (see ``_OPS``).
    value : Any
        Right-hand-side value to compare against.
    description : str
        Human-readable description of the rule.
    """

    rule_type: RuleType
    field_path: str
    operator: str
    value: Any
    description: str = ""


@dataclass
class ABACPolicy:
    """An ordered collection of ABAC rules that together describe when access
    is **allowed**.

    All rules in a policy must evaluate to *True* for the policy to grant
    access (logical AND).  If *any* policy matches, the request is allowed
    (logical OR across policies).

    Parameters
    ----------
    name : str
        Human-readable policy name.
    rules : list[ABACRule]
        Ordered list of rules (all must pass).
    priority : int
        Higher-priority policies are evaluated first.  Default 0.
    effect : str
        ``"allow"`` or ``"deny"``.  Deny policies override allows.
    description : str
        Human-readable policy description.
    """

    name: str
    rules: list[ABACRule] = field(default_factory=list)
    priority: int = 0
    effect: str = "allow"
    description: str = ""


# ---------------------------------------------------------------------------
# Helper: resolve a dot-separated path on a nested dict
# ---------------------------------------------------------------------------


def _resolve_path(context: dict[str, Any], path: str) -> Any:
    """Walk *path* (e.g. ``"resource.clearance_level"``) on *context*.

    Returns ``None`` if any segment is missing.
    """
    current: Any = context
    for part in path.split("."):
        current = current.get(part) if isinstance(current, dict) else getattr(current, part, None)
        if current is None:
            return None
    return current


# ---------------------------------------------------------------------------
# ABAC Policy Engine
# ---------------------------------------------------------------------------


class ABACPolicyEngine:
    """Attribute-Based Access Control policy engine.

    Evaluates requests against an ordered list of :class:`ABACPolicy` objects.
    The decision algorithm:

    1. Sort policies by descending *priority*.
    2. For each policy, evaluate every rule (AND within a policy).
    3. If a **deny** policy matches → DENY immediately.
    4. If an **allow** policy matches → ALLOW.
    5. If no policy matches → DENY (default-deny).
    """

    def __init__(self, policies: list[ABACPolicy] | None = None) -> None:
        self._policies: list[ABACPolicy] = policies or []

    # -- policy management ---------------------------------------------------

    def add_policy(self, policy: ABACPolicy | list[ABACPolicy]) -> None:
        """Add one or more policies to the engine.

        If a list is passed (e.g. the return value of
        :func:`make_business_hours_policy`), each policy in the list is
        flattened into the engine individually. This prevents the bug where
        ``engine.add_policy(make_business_hours_policy(...))`` would store the
        whole list as a single element of ``_policies`` and then crash with
        ``AttributeError: 'list' object has no attribute 'priority'`` when
        sorting.
        """
        # Flatten: accept either a single ABACPolicy or a list of them.
        if isinstance(policy, list):
            for p in policy:
                self.add_policy(p)
            return

        self._policies.append(policy)
        self._policies.sort(key=lambda p: p.priority, reverse=True)
        logger.info(
            "ABAC policy added: %s (priority=%d, effect=%s)",
            policy.name,
            policy.priority,
            policy.effect,
        )

    def remove_policy(self, name: str) -> bool:
        """Remove a policy by name.  Returns ``True`` if found & removed."""
        before = len(self._policies)
        self._policies = [p for p in self._policies if p.name != name]
        removed = len(self._policies) < before
        if removed:
            logger.info("ABAC policy removed: %s", name)
        return removed

    def list_policies(self) -> list[str]:
        """Return names of all registered policies in priority order."""
        return [p.name for p in self._policies]

    # -- rule evaluation -----------------------------------------------------

    @staticmethod
    def _evaluate_rule(
        rule: ABACRule, subject: dict, action: str, resource: dict, environment: dict,
    ) -> bool:
        """Evaluate a single rule against the request context.

        The *field_path* is resolved against the appropriate context bucket
        depending on *rule_type*.
        """
        # Select the context dict based on rule type
        if rule.rule_type == RuleType.ROLE:
            context: dict[str, Any] = {"role": subject.get("role", ""), **subject}
        elif rule.rule_type == RuleType.ATTRIBUTE:
            context = subject
        elif rule.rule_type == RuleType.RESOURCE:
            context = {"resource": resource, **resource}
        elif rule.rule_type == RuleType.TIME or rule.rule_type == RuleType.IP:
            context = environment
        else:
            logger.warning("Unknown ABAC rule type: %s", rule.rule_type)
            return False

        actual = _resolve_path(context, rule.field_path)
        if actual is None:
            return False

        # Resolve template values like ${subject.clearance_level}
        resolved_value = rule.value
        if (
            isinstance(resolved_value, str)
            and resolved_value.startswith("${")
            and resolved_value.endswith("}")
        ):
            template_path = resolved_value[2:-1]  # Strip ${ and }
            if template_path.startswith("subject."):
                resolved_value = _resolve_path(subject, template_path[len("subject.") :])
            elif template_path.startswith("resource."):
                resolved_value = _resolve_path(resource, template_path[len("resource.") :])
            elif template_path.startswith("environment."):
                resolved_value = _resolve_path(environment, template_path[len("environment.") :])
            if resolved_value is None:
                return False

        op_fn = _OPS.get(rule.operator)
        if op_fn is None:
            logger.warning("Unknown ABAC operator: %s", rule.operator)
            return False

        try:
            return op_fn(actual, resolved_value)
        except (TypeError, ValueError) as exc:
            logger.debug("ABAC rule evaluation error: %s", exc)
            return False

    def _evaluate_policy(
        self,
        policy: ABACPolicy,
        subject: dict,
        action: str,
        resource: dict,
        environment: dict,
    ) -> bool:
        """Evaluate all rules in a policy (logical AND)."""
        if not policy.rules:
            # Empty policy with no rules is treated as not matching
            return False
        for rule in policy.rules:
            if not self._evaluate_rule(rule, subject, action, resource, environment):
                logger.debug(
                    "Policy '%s' blocked by rule: %s %s %s",
                    policy.name,
                    rule.field_path,
                    rule.operator,
                    rule.value,
                )
                return False
        return True

    # -- main decision -------------------------------------------------------

    def evaluate(
        self,
        subject: dict,
        action: str,
        resource: dict,
        environment: dict,
    ) -> bool:
        """Evaluate ABAC policy: Subject + Action + Resource + Environment → Allow/Deny.

        Parameters
        ----------
        subject : dict
            Attributes of the requesting entity (user).  Must include at least
            ``"role"``.  May include ``"department"``, ``"region"``,
            ``"clearance_level"``, etc.
        action : str
            The action being attempted (e.g. ``"run_study"``).
        resource : dict
            Attributes of the target resource (e.g.
            ``{"clearance_level": 3, "owner": "power_systems"}``).
        environment : dict
            Environmental context.  Expected keys:
            ``"time"`` (a :class:`datetime`), ``"ip"`` (str), and any
            additional contextual attributes.

        Returns
        -------
        bool
            ``True`` if access is allowed, ``False`` if denied.
        """
        # Ensure environment has sensible defaults
        env = dict(environment)
        if "time" not in env:
            env["time"] = datetime.now(UTC)

        # Normalise time into convenient attributes if a datetime is given
        if isinstance(env.get("time"), datetime):
            t: datetime = env["time"]
            env.setdefault("hour", t.hour)
            env.setdefault("day_of_week", t.weekday())
            env.setdefault("is_business_hours", 8 <= t.hour <= 18)

        # Evaluate policies in priority order
        allow_matched = False
        for policy in self._policies:
            if not self._evaluate_policy(policy, subject, action, resource, env):
                continue

            # Policy matched — apply effect
            if policy.effect == "deny":
                logger.warning(
                    "ABAC DENY by policy '%s' for subject=%s action=%s",
                    policy.name,
                    subject.get("role"),
                    action,
                )
                return False  # explicit deny is final

            if policy.effect == "allow":
                allow_matched = True
                logger.debug(
                    "ABAC ALLOW by policy '%s' for subject=%s action=%s",
                    policy.name,
                    subject.get("role"),
                    action,
                )

        if allow_matched:
            return True

        # Default: DENY all unless explicitly allowed
        logger.info(
            "ABAC default DENY for subject=%s action=%s (no matching allow policy)",
            subject.get("role"),
            action,
        )
        return False


# ---------------------------------------------------------------------------
# IP range helper
# ---------------------------------------------------------------------------


def ip_in_ranges(ip_str: str, allowed_ranges: Sequence[str]) -> bool:
    """Check whether *ip_str* falls within any of the CIDR *allowed_ranges*.

    Parameters
    ----------
    ip_str : str
        The IP address to check (e.g. ``"10.0.1.5"``).
    allowed_ranges : sequence of str
        CIDR notation ranges (e.g. ``["10.0.0.0/8", "192.168.0.0/16"]``).

    Returns
    -------
    bool
    """
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    for cidr in allowed_ranges:
        try:
            if addr in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


# ---------------------------------------------------------------------------
# FastAPI Middleware
# ---------------------------------------------------------------------------

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    _HAS_STARLETTE = True
except ImportError:
    _HAS_STARLETTE = False


if _HAS_STARLETTE:

    class ABACMiddleware(BaseHTTPMiddleware):
        """FastAPI / Starlette middleware for ABAC enforcement.

        Extracts subject attributes from JWT claims, builds the
        action/resource/environment context, and delegates to
        :class:`ABACPolicyEngine`.  Requests that fail evaluation receive
        a ``403 Forbidden`` response.

        Parameters
        ----------
        policies : list[ABACPolicy]
            Policies to load into the engine.
        jwt_decode_fn : callable, optional
            Async callable that accepts a token string and returns a dict of
            claims.  If not provided, the middleware expects the
            ``Authorization: Bearer <token>`` header and uses the
            :mod:`jwt` library with ``JWT_SECRET_KEY`` from the environment.
        public_paths : list[str], optional
            Path prefixes that bypass ABAC checks (e.g. ``["/health", "/docs"]``).
        """

        def __init__(
            self,
            app: Any,
            policies: list[ABACPolicy] | None = None,
            jwt_decode_fn: Callable[..., Any] | None = None,
            public_paths: list[str] | None = None,
        ) -> None:
            super().__init__(app)
            self.engine = ABACPolicyEngine(policies or [])
            self._jwt_decode_fn = jwt_decode_fn
            self._public_paths = public_paths or ["/health", "/docs", "/openapi.json"]

        def add_policy(self, policy: ABACPolicy) -> None:
            """Add a policy at runtime."""
            self.engine.add_policy(policy)

        async def _decode_jwt(self, token: str) -> dict[str, Any]:
            """Decode a JWT token into claims dict."""
            if self._jwt_decode_fn is not None:
                return await self._jwt_decode_fn(token)

            import os

            import jwt as _jwt

            secret = os.environ.get("JWT_SECRET_KEY", "")
            if not secret:
                logger.warning("JWT_SECRET_KEY not set; ABAC middleware cannot validate tokens")
                return {}
            try:
                payload = _jwt.decode(token, secret, algorithms=["HS256"])
                return payload
            except _jwt.InvalidTokenError:
                return {}

        async def dispatch(self, request: Request, call_next: Any) -> Any:
            """Intercept each request and enforce ABAC."""
            # Skip public paths
            path = request.url.path
            if any(path.startswith(prefix) for prefix in self._public_paths):
                return await call_next(request)

            # Extract subject from JWT
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing or invalid Authorization header"},
                )

            token = auth_header[7:]
            claims = await self._decode_jwt(token)
            if not claims:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or expired token"},
                )

            # Build ABAC context
            subject: dict[str, Any] = {
                "user_id": claims.get("user_id", ""),
                "role": claims.get("role", "guest"),
                "department": claims.get("department", ""),
                "region": claims.get("region", ""),
                "clearance_level": claims.get("clearance_level", 0),
            }

            # Derive action from HTTP method + path
            action = f"{request.method.lower()}:{path}"

            # Resource: query params + path info
            resource: dict[str, Any] = {
                "path": path,
                "method": request.method,
                "clearance_level": 0,  # default; override per-route as needed
            }

            # Environment
            client_ip = request.client.host if request.client else "0.0.0.0"
            environment: dict[str, Any] = {
                "time": datetime.now(UTC),
                "ip": client_ip,
                "source": "abac_middleware",
            }

            allowed = self.engine.evaluate(subject, action, resource, environment)
            if not allowed:
                logger.warning(
                    "ABAC denied: subject=%s action=%s ip=%s",
                    subject.get("role"),
                    action,
                    client_ip,
                )
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Access denied by ABAC policy"},
                )

            return await call_next(request)

else:
    # Stub when Starlette/FastAPI is not installed
    class ABACMiddleware:  # type: ignore[no-redef]
        """Placeholder when Starlette is not available."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            logger.warning("ABACMiddleware requires Starlette/FastAPI; install starlette to enable")


# ---------------------------------------------------------------------------
# Policy builder helpers
# ---------------------------------------------------------------------------


def make_role_policy(
    name: str,
    allowed_roles: list[str],
    actions: list[str] | None = None,
    priority: int = 10,
) -> ABACPolicy:
    """Create a policy that allows subjects with a role in *allowed_roles*.

    Parameters
    ----------
    name : str
        Policy name.
    allowed_roles : list[str]
        Roles that are permitted.
    actions : list[str], optional
        If given, only these actions are allowed.  If ``None``, all actions
        are considered.
    priority : int
        Policy priority (default 10).

    Returns
    -------
    ABACPolicy
    """
    rules: list[ABACRule] = [
        ABACRule(
            rule_type=RuleType.ROLE,
            field_path="role",
            operator="in",
            value=allowed_roles,
            description=f"Role must be one of {allowed_roles}",
        ),
    ]
    if actions:
        rules.append(
            ABACRule(
                rule_type=RuleType.ATTRIBUTE,
                field_path="action",
                operator="in",
                value=actions,
                description=f"Action must be one of {actions}",
            ),
        )
    return ABACPolicy(name=name, rules=rules, priority=priority, effect="allow")


def make_business_hours_policy(
    name: str = "business_hours_only",
    start_hour: int = 8,
    end_hour: int = 18,
    priority: int = 5,
) -> list[ABACPolicy]:
    """Create deny policies that block access outside business hours.

    Parameters
    ----------
    name : str
        Policy name prefix.
    start_hour : int
        Start of allowed window (24-h, inclusive).
    end_hour : int
        End of allowed window (24-h, inclusive).
    priority : int
        Policy priority (default 5).

    Returns
    -------
    list[ABACPolicy]
        Two **deny** policies: one for before start_hour, one for after end_hour.
    """
    return [
        ABACPolicy(
            name=f"{name}_before",
            rules=[
                ABACRule(
                    rule_type=RuleType.TIME,
                    field_path="hour",
                    operator="<",
                    value=start_hour,
                    description=f"Before business hours (hour < {start_hour})",
                ),
            ],
            priority=priority,
            effect="deny",
            description=f"Deny access before {start_hour}:00",
        ),
        ABACPolicy(
            name=f"{name}_after",
            rules=[
                ABACRule(
                    rule_type=RuleType.TIME,
                    field_path="hour",
                    operator=">",
                    value=end_hour,
                    description=f"After business hours (hour > {end_hour})",
                ),
            ],
            priority=priority,
            effect="deny",
            description=f"Deny access after {end_hour}:00",
        ),
    ]


def make_ip_allowlist_policy(
    name: str,
    allowed_cidrs: list[str],
    priority: int = 20,
) -> ABACPolicy:
    """Create an allow policy restricted to IP CIDR ranges.

    Parameters
    ----------
    name : str
        Policy name.
    allowed_cidrs : list[str]
        CIDR ranges (e.g. ``["10.0.0.0/8"]``).
    priority : int
        Policy priority (default 20).

    Returns
    -------
    ABACPolicy
    """
    return ABACPolicy(
        name=name,
        rules=[
            ABACRule(
                rule_type=RuleType.IP,
                field_path="ip",
                operator="in",
                value=allowed_cidrs,
                description=f"IP must be in {allowed_cidrs}",
            ),
        ],
        priority=priority,
        effect="allow",
        description=f"Allow from IP ranges: {allowed_cidrs}",
    )


def make_clearance_policy(
    name: str = "clearance_check",
    priority: int = 15,
) -> ABACPolicy:
    """Create an allow policy requiring ``resource.clearance_level <= subject.clearance_level``.

    Parameters
    ----------
    name : str
        Policy name.
    priority : int
        Policy priority (default 15).

    Returns
    -------
    ABACPolicy
    """
    return ABACPolicy(
        name=name,
        rules=[
            ABACRule(
                rule_type=RuleType.RESOURCE,
                field_path="clearance_level",
                operator="<=",
                value="${subject.clearance_level}",
                description="Subject clearance must be >= resource clearance",
            ),
        ],
        priority=priority,
        effect="allow",
        description="Resource clearance level check",
    )


# ---------------------------------------------------------------------------
# Convenience: engine with ETAP default policies
# ---------------------------------------------------------------------------


def create_default_etap_abac_engine() -> ABACPolicyEngine:
    """Create an :class:`ABACPolicyEngine` pre-loaded with ETAP platform defaults.

    Default policies:

    1. **admin_full_access** — admins can do everything (priority 100).
    2. **engineer_studies** — engineers may run studies (priority 50).
    3. **analyst_read** — analysts may read data (priority 50).
    4. **viewer_read** — viewers may read data (priority 40).
    5. **internal_network** — allow from internal IP ranges (priority 30).
    6. **business_hours_deny** — deny outside 08:00–18:00 (priority 5).

    Returns
    -------
    ABACPolicyEngine
    """
    engine = ABACPolicyEngine()

    # Admin full access
    engine.add_policy(
        make_role_policy(
            name="admin_full_access",
            allowed_roles=["admin"],
            priority=100,
        ),
    )

    # Engineer can run studies
    engine.add_policy(
        make_role_policy(
            name="engineer_studies",
            allowed_roles=["engineer"],
            actions=[
                "get:/api/studies",
                "post:/api/studies",
                "get:/api/projects",
                "post:/api/projects",
            ],
            priority=50,
        ),
    )

    # Analyst read
    engine.add_policy(
        make_role_policy(
            name="analyst_read",
            allowed_roles=["analyst"],
            actions=[
                "get:/api/studies",
                "get:/api/projects",
            ],
            priority=50,
        ),
    )

    # Viewer read
    engine.add_policy(
        make_role_policy(
            name="viewer_read",
            allowed_roles=["viewer"],
            actions=[
                "get:/api/studies",
                "get:/api/projects",
            ],
            priority=40,
        ),
    )

    # Internal network allow
    engine.add_policy(
        make_ip_allowlist_policy(
            name="internal_network",
            allowed_cidrs=["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],
            priority=30,
        ),
    )

    # Business hours deny
    for policy in make_business_hours_policy(
        name="business_hours_deny",
        start_hour=8,
        end_hour=18,
        priority=5,
    ):
        engine.add_policy(policy)

    return engine
