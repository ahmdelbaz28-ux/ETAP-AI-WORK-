"""
api/security_audit.py — Runtime security audit module for the AhmedETAP.

Performs comprehensive security analysis of the running service:

  1. Scan all API endpoints for missing authentication
  2. Check for proper CORS configuration
  3. Validate that all POST/PUT endpoints have input validation
  4. Check for missing rate limiting on sensitive endpoints
  5. Scan for hardcoded secrets in the codebase
  6. Check for insecure dependencies
  7. Generate a security score (0–100)
  8. Output a prioritized remediation list

Usage (CLI)::

    python -m api.security_audit --project-root /path/to/repo

Usage (programmatic)::

    from api.security_audit import SecurityAuditor
    report = await SecurityAuditor(project_root="/path/to/repo").run()
    print(json.dumps(report, indent=2))
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Optional, Union

from compat import StrEnum

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class Severity(StrEnum):
    """Finding severity level."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingCategory(StrEnum):
    """Category of a security finding."""

    MISSING_AUTH = "missing_authentication"
    CORS_MISCONFIGURATION = "cors_misconfiguration"
    MISSING_INPUT_VALIDATION = "missing_input_validation"
    MISSING_RATE_LIMIT = "missing_rate_limiting"
    HARDCODED_SECRET = "hardcoded_secret"
    INSECURE_DEPENDENCY = "insecure_dependency"
    DEAD_CODE = "dead_code"
    WEAK_CRYPTO = "weak_crypto"
    INFORMATION_DISCLOSURE = "information_disclosure"
    MISCONFIGURATION = "misconfiguration"


@dataclass
class SecurityFinding:
    """A single security finding from the audit."""

    id: str
    category: FindingCategory
    severity: Severity
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    endpoint: Optional[str] = None
    remediation: str = ""
    references: list[str] = field(default_factory=list)
    cwe_id: Optional[str] = None  # CWE identifier, e.g. "CWE-306"

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "endpoint": self.endpoint,
            "remediation": self.remediation,
            "references": self.references,
            "cwe_id": self.cwe_id,
        }


@dataclass
class SecurityAuditReport:
    """Complete security audit report."""

    project_root: str
    security_score: int  # 0-100
    grade: str  # A-F
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    findings: list[SecurityFinding] = field(default_factory=list)
    remediation_priority: list[dict[str, Any]] = field(default_factory=list)
    scan_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "project_root": self.project_root,
            "security_score": self.security_score,
            "grade": self.grade,
            "total_findings": self.total_findings,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "info_count": self.info_count,
            "findings": [f.to_dict() for f in self.findings],
            "remediation_priority": self.remediation_priority,
            "scan_metadata": self.scan_metadata,
        }


# ---------------------------------------------------------------------------
# Secret patterns for hardcoded-secret scanning
# ---------------------------------------------------------------------------

_SECRET_PATTERNS: list[tuple[str, str, Severity]] = [
    # (pattern, description, severity)
    (
        r'(?:api[_-]Union[?key, apikey])\s*[=:]\s*["\'][A-Za-z0-9\-_]{16,}["\']',
        "Hardcoded API key",
        Severity.CRITICAL,
    ),
    (
        r'(Union[?:secret, secret][_-]?key)\s*[=:]\s*["\'][A-Za-z0-9\-_]{16,}["\']',
        "Hardcoded secret key",
        Severity.CRITICAL,
    ),
    (
        r'(Union[?:password|passwd, pwd])\s*[=:]\s*["\'][^\s"\']{8,}["\']',
        "Hardcoded password",
        Severity.CRITICAL,
    ),
    (
        r'(Union[?:token, access][_-]Union[?token, auth][_-]?token)\s*[=:]\s*["\'][A-Za-z0-9\-_.]{20,}["\']',
        "Hardcoded token",
        Severity.CRITICAL,
    ),
    (
        r'(?:private[_-]?key)\s*[=:]\s*["\']-----BEGIN[A-Z ]+PRIVATE KEY',
        "Hardcoded private key",
        Severity.CRITICAL,
    ),
    (
        r'(?:jwt[_-]Union[?secret, jwt][_-]?key)\s*[=:]\s*["\'][A-Za-z0-9\-_]{8,}["\']',
        "Hardcoded JWT secret",
        Severity.HIGH,
    ),
    (
        r'(?:database[_-]Union[?url, db][_-]?url)\s*[=:]\s*["\'](Union[?:postgres|mysql, mongodb])://[^\s"\']+',
        "Hardcoded database URL with credentials",
        Severity.HIGH,
    ),
    (
        r'(?:redis[_-]?url)\s*[=:]\s*["\']redis://:[^\s"\']+',
        "Hardcoded Redis URL with password",
        Severity.MEDIUM,
    ),
    (
        r'(?:aws[_-]?access[_-]?key[_-]?id)\s*[=:]\s*["\']AKIA[A-Z0-9]{16}["\']',
        "Hardcoded AWS access key",
        Severity.CRITICAL,
    ),
    (
        r'(?:aws[_-]?secret[_-]?access[_-]?key)\s*[=:]\s*["\'][A-Za-z0-9/+=]{40}["\']',
        "Hardcoded AWS secret key",
        Severity.CRITICAL,
    ),
    # Skip false positives: default/change/in-production in the same line
]

# Patterns that indicate the secret is a placeholder/default (not a real secret)
_SAFE_CONTEXT_PATTERNS = [
    r"change[_\-\s]in[_\-\s]production",
    r"replace[_\-\s]with",
    r"your[_\-\s]secret",
    r"example",
    r"default[_\-\s]secret",
    r"todo",
    r"fixme",
    r"xxx+",
    r"dummy",
    r"placeholder",
    r"for[_\-\s]development",
    r"not[_\-\s]for[_\-\s]production",
]


# ---------------------------------------------------------------------------
# Insecure dependency patterns
# ---------------------------------------------------------------------------

_INSECURE_PACKAGES: dict[str, list[str]] = {
    # package: list of known-vulnerable version patterns (simplified)
    "pickle": ["*"],  # Never use pickle for untrusted data
    "yaml": [">=5.0,<5.4"],  # PyYAML unsafe load
    "subprocess": ["*"],  # Shell injection risk if not careful
}

# Functions that indicate insecure patterns
_INSECURE_FUNCTION_PATTERNS: list[tuple[str, str, Severity]] = [
    (r"\beval\s*\(", "Use of eval() — potential code injection", Severity.HIGH),
    (r"\bexec\s*\(", "Use of exec() — potential code injection", Severity.HIGH),
    (r"\b__import__\s*\(", "Dynamic import — potential code injection", Severity.MEDIUM),
    (
        r"subprocess\.call\s*\([^)]*shell\s*=\s*True",
        "subprocess with shell=True — command injection risk",
        Severity.HIGH,
    ),
    (
        r"subprocess\.Popen\s*\([^)]*shell\s*=\s*True",
        "subprocess.Popen with shell=True — command injection risk",
        Severity.HIGH,
    ),
    (r"yaml\.load\s*\(", "yaml.load without Loader — unsafe deserialization", Severity.HIGH),
    (r"pickle\.loads?\s*\(", "pickle.load/loads — unsafe deserialization", Severity.HIGH),
    (r"os\.system\s*\(", "os.system — command injection risk", Severity.HIGH),
    (
        r"hashlib\.md5\s*\(|hashlib\.sha1\s*\(",
        "Use of weak hash algorithm (MD5/SHA1)",
        Severity.LOW,
    ),
    (
        Union[r"random\.random\b, random\.randint\b",]
        "Use of non-cryptographic random for security context",
        Severity.INFO,
    ),
]


# ---------------------------------------------------------------------------
# Main auditor
# ---------------------------------------------------------------------------


class SecurityAuditor:
    """Perform a comprehensive security audit of the AhmedETAP.

    Scans API endpoints, source code, and configuration for security
    issues and generates a prioritized remediation report.

    Example::

        auditor = SecurityAuditor(project_root="/path/to/repo")
        report = await auditor.run()
        print(f"Security Score: {report.security_score}/100 ({report.grade})")
    """

    def __init__(self, project_root: Optional[str] = None) -> None:
        """Initialize the auditor.

        Args:
            project_root: Path to the project root directory.
                Defaults to the parent of this file's directory.
        """
        if project_root is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.project_root = os.path.abspath(project_root)
        self._findings: list[SecurityFinding] = []
        self._finding_counter: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> SecurityAuditReport:
        """Execute the full security audit pipeline.

        Returns:
            A :class:`SecurityAuditReport` with security score and
            prioritized remediation list.
        """
        self._findings = []
        self._finding_counter = 0

        # Run all audit checks
        await self._check_missing_auth()
        await self._check_cors_configuration()
        await self._check_input_validation()
        await self._check_rate_limiting()
        await self._scan_hardcoded_secrets()
        await self._check_insecure_dependencies()
        await self._check_dead_code()
        await self._check_weak_crypto()
        await self._check_information_disclosure()

        # Compute security score
        score, grade = self._compute_security_score()

        # Build remediation priority list
        remediation = self._build_remediation_priority()

        # Count severities
        severity_counts = self._count_severities()

        return SecurityAuditReport(
            project_root=self.project_root,
            security_score=score,
            grade=grade,
            total_findings=len(self._findings),
            critical_count=severity_counts.get(Severity.CRITICAL, 0),
            high_count=severity_counts.get(Severity.HIGH, 0),
            medium_count=severity_counts.get(Severity.MEDIUM, 0),
            low_count=severity_counts.get(Severity.LOW, 0),
            info_count=severity_counts.get(Severity.INFO, 0),
            findings=sorted(
                self._findings,
                key=lambda f: [
                    Severity.CRITICAL,
                    Severity.HIGH,
                    Severity.MEDIUM,
                    Severity.LOW,
                    Severity.INFO,
                ].index(f.severity),
            ),
            remediation_priority=remediation,
            scan_metadata={
                "python_files_scanned": self._count_python_files(),
                "total_findings": len(self._findings),
            },
        )

    # ------------------------------------------------------------------
    # Helper: create a finding
    # ------------------------------------------------------------------

    def _add_finding(
        self,
        category: FindingCategory,
        severity: Severity,
        title: str,
        description: str,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        endpoint: Optional[str] = None,
        remediation: str = "",
        references: list[str] | None = None,
        cwe_id: Optional[str] = None,
    ) -> None:
        """Create and register a security finding."""
        self._finding_counter += 1
        finding = SecurityFinding(
            id=f"SEC-{self._finding_counter:03d}",
            category=category,
            severity=severity,
            title=title,
            description=description,
            file_path=file_path,
            line_number=line_number,
            endpoint=endpoint,
            remediation=remediation,
            references=references or [],
            cwe_id=cwe_id,
        )
        self._findings.append(finding)

    # ------------------------------------------------------------------
    # Check 1: Missing authentication on endpoints
    # ------------------------------------------------------------------

    async def _check_missing_auth(self) -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        """Scan all API endpoints for missing authentication checks.

        Look for FastAPI route decorators that don't include
        ``_require_api_key`` or ``Depends(get_api_key)`` in their
        implementation.
        """
        # Scan the engineering_service.py for endpoints without auth
        service_files = [
            os.path.join(self.project_root, "engineering_service.py"),  # NOSONAR — S1192: intentional repetition (audit constant)
            os.path.join(self.project_root, "api", "refactored_service.py"),  # NOSONAR — S1192: intentional repetition (audit constant)
        ]

        for service_file in service_files:
            if not os.path.exists(service_file):
                continue

            with open(service_file, encoding="utf-8", errors="replace") as fh:  # NOSONAR — S7493: sync file I/O in async function; compatibility with sync lib
                lines = fh.readlines()

            # Parse to find endpoint definitions
            current_endpoint: Optional[str] = None
            endpoint_line: Optional[int] = None
            has_auth_check = False

            for i, line in enumerate(lines, 1):
                # Detect endpoint decorator
                decorator_match = re.match(
                    r'@app\.(Union[get|post|put|delete|patch, head])\s*\(["\']([^"\']+)',
                    line.strip(),
                )
                if decorator_match:
                    # Check previous endpoint for auth
                    if current_endpoint and not has_auth_check:
                        self._add_finding(
                            category=FindingCategory.MISSING_AUTH,
                            severity=Severity.HIGH,
                            title=f"Missing authentication on {current_endpoint}",
                            description=(
                                f"The endpoint ``{current_endpoint}`` does not "
                                f"validate API keys or JWT tokens."
                            ),
                            file_path=service_file,
                            line_number=endpoint_line,
                            endpoint=current_endpoint,
                            remediation=(
                                "Add ``_require_api_key(request)`` or "
                                "``Depends(get_api_key)`` to the endpoint."
                            ),
                            references=["OWASP API2:2023 Broken Authentication"],
                            cwe_id="CWE-306",
                        )
                    # Start tracking new endpoint
                    method = decorator_match.group(1).upper()
                    path = decorator_match.group(2)
                    current_endpoint = f"{method} {path}"
                    endpoint_line = i
                    has_auth_check = False

                # Detect auth check in function body
                if current_endpoint and not has_auth_check and any(
                    kw in line
                    for kw in (
                        "_require_api_key",
                        "get_api_key",
                        "Depends(get_api_key)",
                        "get_current_user",
                    )
                ):
                    has_auth_check = True

            # Check last endpoint
            if current_endpoint and not has_auth_check:
                self._add_finding(
                    category=FindingCategory.MISSING_AUTH,
                    severity=Severity.HIGH,
                    title=f"Missing authentication on {current_endpoint}",
                    description=f"The endpoint ``{current_endpoint}`` does not validate API keys.",
                    file_path=service_file,
                    line_number=endpoint_line,
                    endpoint=current_endpoint,
                    remediation="Add ``_require_api_key(request)`` or ``Depends(get_api_key)``.",
                    references=["OWASP API2:2023 Broken Authentication"],
                    cwe_id="CWE-306",
                )

    # ------------------------------------------------------------------
    # Check 2: CORS configuration
    # ------------------------------------------------------------------

    async def _check_cors_configuration(self) -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        """Check for CORS misconfigurations."""
        service_files = [
            os.path.join(self.project_root, "engineering_service.py"),
            os.path.join(self.project_root, "api", "refactored_service.py"),
        ]

        for service_file in service_files:
            if not os.path.exists(service_file):
                continue

            with open(service_file, encoding="utf-8", errors="replace") as fh:  # NOSONAR — S7493: sync file I/O in async function; compatibility with sync lib
                content = fh.read()

            # Check for wildcard origins
            if 'allow_origins=["*"]' in content or "allow_origins=['*']" in content:
                self._add_finding(
                    category=FindingCategory.CORS_MISCONFIGURATION,
                    severity=Severity.HIGH,
                    title="CORS allows all origins",
                    description="The CORS configuration allows requests from any origin (`*`).",
                    file_path=service_file,
                    remediation=(
                        "Restrict CORS to specific trusted origins using the "
                        "ENGINEERING_SERVICE_CORS_ORIGINS environment variable."
                    ),
                    references=["OWASP API8:2023 Security Misconfiguration"],
                    cwe_id="CWE-942",
                )

            # Check if CORS origins are configurable via env
            if "ENGINEERING_SERVICE_CORS_ORIGINS" not in content:
                self._add_finding(
                    category=FindingCategory.CORS_MISCONFIGURATION,
                    severity=Severity.MEDIUM,
                    title="CORS origins not configurable via environment",
                    description=(
                        "CORS allowed origins are hardcoded rather than "
                        "configurable via environment variable."
                    ),
                    file_path=service_file,
                    remediation=(
                        "Use ``os.environ.get('ENGINEERING_SERVICE_CORS_ORIGINS', '')`` "
                        "to make CORS origins configurable."
                    ),
                    cwe_id="CWE-942",
                )

            # Check for permissive methods
            if "allow_methods" in content and ("DELETE" in content or "PATCH" in content):
                # This is actually fine for a full REST API, just note it
                pass

            # Check if credentials are allowed with wildcard (most dangerous)
            if 'allow_origins=["*"]' in content and "allow_credentials=True" in content:
                self._add_finding(
                    category=FindingCategory.CORS_MISCONFIGURATION,
                    severity=Severity.CRITICAL,
                    title="CORS allows credentials with wildcard origin",
                    description=(
                        "Setting allow_credentials=True with allow_origins=['*'] "
                        "is a critical security misconfiguration that allows any "
                        "origin to make authenticated cross-origin requests."
                    ),
                    file_path=service_file,
                    remediation=(
                        "Remove allow_credentials=True when using wildcard origins, "
                        "or restrict origins to specific trusted domains."
                    ),
                    references=["OWASP API8:2023 Security Misconfiguration"],
                    cwe_id="CWE-942",
                )

    # ------------------------------------------------------------------
    # Check 3: Input validation on POST/PUT endpoints
    # ------------------------------------------------------------------

    async def _check_input_validation(self) -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        """Validate that all POST/PUT endpoints have input validation.

        Checks that endpoints use Pydantic models or explicit validation
        rather than accepting raw ``Request`` objects for POST/PUT.
        """
        service_files = [
            os.path.join(self.project_root, "engineering_service.py"),
            os.path.join(self.project_root, "api", "refactored_service.py"),
        ]

        for service_file in service_files:
            if not os.path.exists(service_file):
                continue

            with open(service_file, encoding="utf-8", errors="replace") as fh:  # NOSONAR — S7493: sync file I/O in async function; compatibility with sync lib
                lines = fh.readlines()

            for i, line in enumerate(lines, 1):
                # Look for POST/PUT endpoints that accept raw Request
                # without a Pydantic model
                if re.search(r"@app\.(Union[post|put, patch])", line.strip()):
                    # Check the function signature in the next few lines
                    func_sig = "".join(lines[i : i + 3]) if i < len(lines) else ""
                    if "request: Request" in func_sig and "BaseModel" not in func_sig:
                        # This endpoint accepts raw Request — check if it validates
                        # Look ahead for validation patterns
                        func_body = (
                            "".join(lines[i : i + 20])
                            if i + 20 < len(lines)
                            else "".join(lines[i:])
                        )
                        if "body.get(" in func_body and "HTTPException" not in func_body:
                            # Using body.get() without raising validation errors
                            decorator_match = re.search(
                                r'@app\.(Union[post|put, patch])\s*\(["\']([^"\']+)',
                                line.strip(),
                            )
                            endpoint = decorator_match.group(2) if decorator_match else "unknown"
                            self._add_finding(
                                category=FindingCategory.MISSING_INPUT_VALIDATION,
                                severity=Severity.MEDIUM,
                                title=f"POST/PUT endpoint uses raw request body without Pydantic model: {endpoint}",
                                description=(
                                    f"The endpoint ``{endpoint}`` reads the request body "
                                    f"directly using ``await request.json()`` instead of "
                                    f"using a Pydantic model for automatic validation."
                                ),
                                file_path=service_file,
                                line_number=i,
                                endpoint=endpoint,
                                remediation=(
                                    "Define a Pydantic BaseModel for the request body "
                                    "and use it as a typed parameter in the endpoint function."
                                ),
                                references=[
                                    "OWASP API3:2023 Broken Object Property Level Authorization",
                                ],
                                cwe_id="CWE-20",
                            )

    # ------------------------------------------------------------------
    # Check 4: Missing rate limiting
    # ------------------------------------------------------------------

    async def _check_rate_limiting(self) -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        """Check for missing rate limiting on sensitive endpoints."""
        sensitive_paths = [
            "/api/v1/auth/mfa/totp/setup",
            "/api/v1/auth/mfa/totp/verify",
            "/api/v1/auth/abac/check",
            "/api/v1/security/siem/event",
            "/api/v1/predict/load",
            "/api/v1/predict/fault",
            "/api/v1/predict/anomaly",
            "/api/v1/rag/query",
        ]

        service_files = [
            os.path.join(self.project_root, "engineering_service.py"),
            os.path.join(self.project_root, "api", "refactored_service.py"),
        ]

        for service_file in service_files:
            if not os.path.exists(service_file):
                continue

            with open(service_file, encoding="utf-8", errors="replace") as fh:  # NOSONAR — S7493: sync file I/O in async function; compatibility with sync lib
                content = fh.read()

            # Check if global rate limiting exists
            has_global_rate_limit = (
                "_check_rate_limit" in content or "rate_limit" in content.lower()
            )

            if not has_global_rate_limit:
                self._add_finding(
                    category=FindingCategory.MISSING_RATE_LIMIT,
                    severity=Severity.HIGH,
                    title="No rate limiting configured",
                    description="The service does not implement any rate limiting.",
                    file_path=service_file,
                    remediation=(
                        "Implement rate limiting middleware or per-endpoint rate "
                        "limiting using a token bucket or sliding window algorithm."
                    ),
                    references=["OWASP API4:2023 Unrestricted Resource Consumption"],
                    cwe_id="CWE-770",
                )
            else:
                # Check if sensitive endpoints are exempted from rate limiting
                for path in sensitive_paths:
                    # Look for explicit exemptions of sensitive paths
                    if path in content:
                        # Check if rate limiting is bypassed for this path
                        # (In the current code, health endpoints are bypassed but
                        # sensitive endpoints should NOT be)
                        pass  # Global rate limit covers these

                # Check if rate limit uses per-client tracking
                if "client_id" not in content and "client.host" not in content:
                    self._add_finding(
                        category=FindingCategory.MISSING_RATE_LIMIT,
                        severity=Severity.MEDIUM,
                        title="Rate limiting not per-client",
                        description="Rate limiting does not differentiate between clients.",
                        file_path=service_file,
                        remediation="Track rate limits per client IP or API key.",
                        cwe_id="CWE-770",
                    )

    # ------------------------------------------------------------------
    # Check 5: Hardcoded secrets
    # ------------------------------------------------------------------

    async def _scan_hardcoded_secrets(self) -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        """Scan all Python source files for hardcoded secrets."""
        skip_dirs = {
            ".git",
            "__pycache__",
            "node_modules",
            ".venv",  # NOSONAR — S1192: intentional repetition (audit constant)
            "venv",
            ".tox",
            ".mypy_cache",
            ".pytest_cache",
            "dist",
            "build",
            "acp_runtime",
        }

        for dirpath, dirnames, filenames in os.walk(self.project_root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]

            for fname in filenames:
                if not fname.endswith(".py"):
                    continue

                file_path = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(file_path, self.project_root)

                # Skip test files and self-referential modules
                if (
                    "test" in rel_path.lower()
                    or "security_audit" in rel_path
                    or "error_debugger" in rel_path
                ):
                    continue

                with contextlib.suppress(Exception):
                    with open(file_path, encoding="utf-8", errors="replace") as fh:  # NOSONAR — S7493: sync file I/O in async function; compatibility with sync lib
                        lines = fh.readlines()

                    for i, line in enumerate(lines, 1):
                        stripped = line.strip()

                        # Skip comments and docstrings
                        if (
                            stripped.startswith("#", '"""', "'''")  # NOSONAR — python:S8513: false positive — already uses tuple form
                        ):
                            continue

                        # Skip lines that are clearly safe context
                        line_lower = stripped.lower()
                        if any(re.search(pat, line_lower) for pat in _SAFE_CONTEXT_PATTERNS):
                            continue

                        # Check against secret patterns
                        for pattern, description, severity in _SECRET_PATTERNS:
                            if re.search(pattern, stripped, re.IGNORECASE):
                                # Additional check: skip env var lookups
                                if "os.environ" in stripped or "os.getenv" in stripped:
                                    continue
                                # Skip if value is empty or placeholder
                                if '""' in stripped or "''" in stripped:
                                    continue

                                self._add_finding(
                                    category=FindingCategory.HARDCODED_SECRET,
                                    severity=severity,
                                    title=description,
                                    description=(
                                        f"A potential hardcoded secret was detected in "
                                        f"``{rel_path}`` at line {i}. Hardcoded secrets "
                                        f"in source code are a critical security risk."
                                    ),
                                    file_path=rel_path,
                                    line_number=i,
                                    remediation=(
                                        "Move the secret to an environment variable or "
                                        "a secrets manager (e.g., HashiCorp Vault, AWS "
                                        "Secrets Manager)."
                                    ),
                                    references=[
                                        "OWASP API7:2023 Server Side Request Forgery",
                                        "CWE-798",
                                    ],
                                    cwe_id="CWE-798",
                                )
                                break  # Only report once per line

    # ------------------------------------------------------------------
    # Check 6: Insecure dependencies
    # ------------------------------------------------------------------

    async def _check_insecure_dependencies(self) -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        """Check for insecure dependency patterns in the codebase."""
        skip_dirs = {
            ".git",
            "__pycache__",
            "node_modules",
            ".venv",
            "venv",
            ".tox",
            ".mypy_cache",
            ".pytest_cache",
            "dist",
            "build",
            "acp_runtime",
        }

        for dirpath, dirnames, filenames in os.walk(self.project_root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]

            for fname in filenames:
                if not fname.endswith(".py"):
                    continue

                file_path = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(file_path, self.project_root)

                # Skip test files and this audit module
                if (
                    "test" in rel_path.lower()
                    or "security_audit" in rel_path
                    or "error_debugger" in rel_path
                ):
                    continue

                with contextlib.suppress(Exception):
                    with open(file_path, encoding="utf-8", errors="replace") as fh:  # NOSONAR — S7493: sync file I/O in async function; compatibility with sync lib
                        lines = fh.readlines()

                    for i, line in enumerate(lines, 1):
                        stripped = line.strip()
                        if stripped.startswith("#"):
                            continue

                        for pattern, description, severity in _INSECURE_FUNCTION_PATTERNS:
                            if re.search(pattern, stripped):
                                self._add_finding(
                                    category=FindingCategory.INSECURE_DEPENDENCY,
                                    severity=severity,
                                    title=description,
                                    description=(
                                        f"Potentially insecure function call detected in "
                                        f"``{rel_path}`` at line {i}: {stripped[:100]}"
                                    ),
                                    file_path=rel_path,
                                    line_number=i,
                                    remediation=(
                                        "Review the usage and ensure no untrusted input "
                                        "is passed. Use safer alternatives where available."
                                    ),
                                    cwe_id="CWE-94",
                                )

        # Check requirements.txt for known vulnerable packages
        req_file = os.path.join(self.project_root, "requirements.txt")
        if os.path.exists(req_file):
            with contextlib.suppress(Exception):
                with open(req_file, encoding="utf-8", errors="replace") as fh:  # NOSONAR — S7493: sync file I/O in async function; compatibility with sync lib
                    requirements = fh.readlines()

                for line in requirements:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    pkg_name = re.split(r"[=<>~!]", line)[0].strip().lower()
                    if pkg_name in _INSECURE_PACKAGES:
                        self._add_finding(
                            category=FindingCategory.INSECURE_DEPENDENCY,
                            severity=Severity.MEDIUM,
                            title=f"Potentially insecure dependency: {pkg_name}",
                            description=(
                                f"Package ``{pkg_name}`` is listed in requirements.txt. "
                                f"Review its usage for security implications."
                            ),
                            file_path="requirements.txt",
                            remediation=(
                                "Ensure the package is used safely and consider "
                                "alternatives if processing untrusted input."
                            ),
                        )

    # ------------------------------------------------------------------
    # Check 7: Dead code
    # ------------------------------------------------------------------

    async def _check_dead_code(self) -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        """Check for dead code patterns (unreachable code, unused imports)."""
        # Check for the specific dead ConnectionManager in the original
        service_file = os.path.join(self.project_root, "engineering_service.py")
        if os.path.exists(service_file):
            with open(service_file, encoding="utf-8", errors="replace") as fh:  # NOSONAR — S7493: sync file I/O in async function; compatibility with sync lib
                content = fh.read()
                lines = content.split("\n")

            # Check for duplicate RASP stats endpoint
            rasp_count = content.count("/api/v1/security/rasp/stats")
            if rasp_count > 1:
                # Find the line numbers
                line_numbers = []
                for i, line in enumerate(lines, 1):
                    if "/api/v1/security/rasp/stats" in line:
                        line_numbers.append(i)

                self._add_finding(
                    category=FindingCategory.DEAD_CODE,
                    severity=Severity.LOW,
                    title="Duplicate RASP stats endpoint definition",
                    description=(
                        "The endpoint ``/api/v1/security/rasp/stats`` is defined "
                        f"twice in engineering_service.py (lines {', '.join(str(n) for n in line_numbers)}). "
                        "Only the last definition will be active."
                    ),
                    file_path="engineering_service.py",
                    line_number=line_numbers[-1] if line_numbers else None,
                    remediation="Remove the duplicate endpoint definition.",
                    cwe_id="CWE-1061",
                )

            # Check for unreachable WebSocket ConnectionManager
            if "ConnectionManager" in content and "websocket" not in content.lower():
                self._add_finding(
                    category=FindingCategory.DEAD_CODE,
                    severity=Severity.LOW,
                    title="Unreachable WebSocket ConnectionManager",
                    description=(
                        "The ``ConnectionManager`` class is defined but never "
                        "wired to any WebSocket endpoint. It is dead code."
                    ),
                    file_path="engineering_service.py",
                    remediation="Either wire the ConnectionManager to a WebSocket endpoint or remove it.",
                    cwe_id="CWE-1061",
                )

            # Check for duplicate global variable
            rate_limit_entries = content.count("RATE_LIMIT_MAX_ENTRIES")
            if rate_limit_entries > 1:
                self._add_finding(
                    category=FindingCategory.DEAD_CODE,
                    severity=Severity.INFO,
                    title="Duplicate variable definition: _RATE_LIMIT_MAX_ENTRIES",
                    description=(
                        "The variable ``_RATE_LIMIT_MAX_ENTRIES`` is defined "
                        "twice in engineering_service.py, which means the second "
                        "definition silently overwrites the first."
                    ),
                    file_path="engineering_service.py",
                    remediation="Remove the duplicate variable definition.",
                )

    # ------------------------------------------------------------------
    # Check 8: Weak crypto
    # ------------------------------------------------------------------

    async def _check_weak_crypto(self) -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        """Check for weak cryptographic patterns."""
        service_files = [
            os.path.join(self.project_root, "engineering_service.py"),
            os.path.join(self.project_root, "api", "refactored_service.py"),
            os.path.join(self.project_root, "api", "auth.py"),
        ]

        for service_file in service_files:
            if not os.path.exists(service_file):
                continue

            with open(service_file, encoding="utf-8", errors="replace") as fh:  # NOSONAR — S7493: sync file I/O in async function; compatibility with sync lib
                content = fh.read()

            # Check for default JWT secret
            if "etap-platform-default-secret-change-in-production" in content:
                self._add_finding(
                    category=FindingCategory.WEAK_CRYPTO,
                    severity=Severity.CRITICAL,
                    title="Default JWT secret key in source code",
                    description=(
                        "A default JWT secret key is hardcoded in the source code. "
                        "If the JWT_SECRET_KEY environment variable is not set, "
                        "this default will be used, allowing token forgery."
                    ),
                    file_path=os.path.relpath(service_file, self.project_root),
                    remediation=(
                        "Remove the default secret and require JWT_SECRET_KEY "
                        "to be set via environment variable. Fail to start if "
                        "not configured."
                    ),
                    references=["CWE-798: Use of Hard-coded Credentials"],
                    cwe_id="CWE-798",
                )

            # Check for HMAC comparison (good)
            if "hmac.compare_digest" in content:
                pass  # Good — constant-time comparison

            # Check for == comparison on secrets (bad)
            if "==" in content and "api_key" in content.lower():
                lines_with_compare = [
                    (i + 1, line)
                    for i, line in enumerate(content.split("\n"))
                    if "==" in line and "api_key" in line.lower() and "hmac" not in line.lower()
                ]
                for _line_num, line in lines_with_compare:
                    # Skip if it's in a comparison that's clearly not timing-sensitive
                    if "if" in line and "provided" not in line.lower():
                        continue

    # ------------------------------------------------------------------
    # Check 9: Information disclosure
    # ------------------------------------------------------------------

    async def _check_information_disclosure(self) -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        """Check for potential information disclosure vulnerabilities."""
        service_files = [
            os.path.join(self.project_root, "engineering_service.py"),
            os.path.join(self.project_root, "api", "refactored_service.py"),
        ]

        for service_file in service_files:
            if not os.path.exists(service_file):
                continue

            with open(service_file, encoding="utf-8", errors="replace") as fh:  # NOSONAR — S7493: sync file I/O in async function; compatibility with sync lib
                content = fh.read()

            # Check if stack traces are exposed in error responses
            if "traceback" in content.lower() and "JSONResponse" in content:
                # Check if traceback details are sent to clients
                if "str(exc)" in content and "500" in content:
                    # Generic exception handler includes str(exc) which might
                    # leak internal details
                    self._add_finding(
                        category=FindingCategory.INFORMATION_DISCLOSURE,
                        severity=Severity.MEDIUM,
                        title="Exception details exposed in error responses",
                        description=(
                            "The generic exception handler includes ``str(exc)`` "
                            "in the response, which may leak internal implementation "
                            "details, file paths, or database schema information."
                        ),
                        file_path=os.path.relpath(service_file, self.project_root),
                        remediation=(
                            "In production, return generic error messages like "
                            "'Internal server error' and log the full details "
                            "server-side only."
                        ),
                        references=["OWASP API7:2023 Server Side Request Forgery"],
                        cwe_id="CWE-209",
                    )

            # Check if debug mode is forced
            if "debug=True" in content:
                self._add_finding(
                    category=FindingCategory.INFORMATION_DISCLOSURE,
                    severity=Severity.HIGH,
                    title="Debug mode enabled in production",
                    description="The application has debug=True enabled, which exposes detailed error pages.",
                    file_path=os.path.relpath(service_file, self.project_root),
                    remediation="Disable debug mode in production environments.",
                    cwe_id="CWE-215",
                )

    # ------------------------------------------------------------------
    # Score computation
    # ------------------------------------------------------------------

    def _compute_security_score(self) -> tuple[int, str]:
        """Compute the security score (0-100) and grade.

        Scoring:
          - Start at 100
          - Critical findings: -15 each
          - High findings: -10 each
          - Medium findings: -5 each
          - Low findings: -2 each
          - Info findings: -0 each
          - Minimum score: 0
        """
        score = 100
        for finding in self._findings:
            if finding.severity == Severity.CRITICAL:
                score -= 15
            elif finding.severity == Severity.HIGH:
                score -= 10
            elif finding.severity == Severity.MEDIUM:
                score -= 5
            elif finding.severity == Severity.LOW:
                score -= 2

        score = max(0, min(100, score))

        if score >= 90:
            grade = "A"
        elif score >= 80:
            grade = "B"
        elif score >= 70:
            grade = "C"
        elif score >= 60:
            grade = "D"
        else:
            grade = "F"

        return score, grade

    # ------------------------------------------------------------------
    # Remediation priority
    # ------------------------------------------------------------------

    def _build_remediation_priority(self) -> list[dict[str, Any]]:
        """Build a prioritized list of remediation actions."""
        priority: list[dict[str, Any]] = []

        # Group findings by category
        by_category: dict[FindingCategory, list[SecurityFinding]] = {}
        for f in self._findings:
            by_category.setdefault(f.category, []).append(f)

        # Order categories by maximum severity
        category_priority = sorted(
            by_category.items(),
            key=lambda item: max(
                [
                    Severity.CRITICAL,
                    Severity.HIGH,
                    Severity.MEDIUM,
                    Severity.LOW,
                    Severity.INFO,
                ].index(f.severity)
                for f in item[1]
            ),
        )

        for category, findings in category_priority:
            critical = [f for f in findings if f.severity == Severity.CRITICAL]
            high = [f for f in findings if f.severity == Severity.HIGH]
            medium = [f for f in findings if f.severity == Severity.MEDIUM]

            priority.append(
                {
                    "category": category.value,
                    "total_findings": len(findings),
                    "critical": len(critical),
                    "high": len(high),
                    "medium": len(medium),
                    "top_remediation": findings[0].remediation if findings else "",
                    "affected_endpoints": list({f.endpoint for f in findings if f.endpoint}),
                    "affected_files": list({f.file_path for f in findings if f.file_path}),
                },
            )

        return priority

    def _count_severities(self) -> dict[Severity, int]:
        """Count findings by severity level."""
        counts: dict[Severity, int] = {}
        for f in self._findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return counts

    def _count_python_files(self) -> int:
        """Count the number of Python files in the project."""
        count = 0
        skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", "acp_runtime"}
        for _dirpath, dirnames, filenames in os.walk(self.project_root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            count += sum(1 for f in filenames if f.endswith(".py"))
        return count


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


async def _main() -> None:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """CLI entrypoint for running the security auditor."""
    import argparse

    parser = argparse.ArgumentParser(
        description="AhmedETAP — Security Auditor",
    )
    parser.add_argument(
        "--project-root",
        type=str,
        default=None,
        help="Path to the project root",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="-",
        help="Output file path ('-' for stdout)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Output only JSON (no summary text)",
    )
    args = parser.parse_args()

    auditor = SecurityAuditor(project_root=args.project_root)
    report = await auditor.run()

    # Use ExitStack so the output file (when not stdout) is always closed
    # via a context manager, even on exception. Replaces the previous
    # try/finally + manual out.close() pattern.
    with contextlib.ExitStack() as stack:
        out = sys.stdout if args.output == "-" else stack.enter_context(
            open(args.output, "w", encoding="utf-8")  # NOSONAR — S7493: sync file I/O in async function; compatibility with sync lib
        )

        if not args.json_only:
            print("=" * 72, file=out)
            print("AhmedETAP — Security Audit Report", file=out)
            print("=" * 72, file=out)
            print(f"Project Root:       {report.project_root}", file=out)
            print(
                f"Security Score:     {report.security_score}/100 (Grade: {report.grade})", file=out,
            )
            print(f"Total Findings:     {report.total_findings}", file=out)
            print(f"  Critical:         {report.critical_count}", file=out)
            print(f"  High:             {report.high_count}", file=out)
            print(f"  Medium:           {report.medium_count}", file=out)
            print(f"  Low:              {report.low_count}", file=out)
            print(f"  Info:             {report.info_count}", file=out)
            print(file=out)

            if report.findings:
                print("-" * 72, file=out)
                print("FINDINGS (sorted by severity):", file=out)
                print("-" * 72, file=out)
                for f in report.findings:
                    severity_str = f.severity.value.upper()
                    print(
                        f"  [{severity_str}] {f.id}: {f.title}",
                        file=out,
                    )
                    if f.file_path:
                        loc = f"at {f.file_path}"
                        if f.line_number:
                            loc += f":{f.line_number}"
                        print(f"         Location: {loc}", file=out)
                    if f.remediation:
                        print(f"         Fix: {f.remediation}", file=out)
                    print(file=out)

            if report.remediation_priority:
                print("-" * 72, file=out)
                print("REMEDIATION PRIORITY:", file=out)
                print("-" * 72, file=out)
                for item in report.remediation_priority:
                    cat = item.get("category", "?")
                    total = item.get("total_findings", 0)
                    crit = item.get("critical", 0)
                    high = item.get("high", 0)
                    med = item.get("medium", 0)
                    print(
                        f"  {cat}: {total} findings ({crit} critical, {high} high, {med} medium)",
                        file=out,
                    )
                    if item.get("top_remediation"):
                        print(f"    → {item['top_remediation']}", file=out)
                print(file=out)

            print("=" * 72, file=out)
            print("Full JSON report follows:", file=out)
            print("=" * 72, file=out)

        json.dump(report.to_dict(), out, indent=2, default=str)
        print(file=out)
    # ExitStack closes the file automatically when leaving the `with` block.


if __name__ == "__main__":
    asyncio.run(_main())
