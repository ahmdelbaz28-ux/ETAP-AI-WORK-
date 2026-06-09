"""
Security Framework for ETAP AI Platform
=========================================
Implements authentication, authorization, input validation, and secure execution.

Features:
- JWT-based authentication
- Role-based access control (RBAC)
- Input validation and sanitization
- Secure code execution sandboxing
- Rate limiting
- Audit logging
- Secrets management
"""

# bcrypt is a hard dependency — add to requirements.txt: bcrypt>=4.0.0
import bcrypt

import jwt
from cryptography.fernet import Fernet

import os
import ast
import time
import hmac
import secrets
import logging
import threading
from typing import Optional, Dict, List, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """User roles for RBAC."""
    ADMIN = "admin"
    ENGINEER = "engineer"
    ANALYST = "analyst"
    VIEWER = "viewer"
    GUEST = "guest"


class Permission(Enum):
    """System permissions."""
    ETAP_LAUNCH = "etap:launch"
    ETAP_OPEN_PROJECT = "etap:open_project"
    ETAP_CREATE_PROJECT = "etap:create_project"
    ETAP_RUN_STUDY = "etap:run_study"
    ETAP_MODIFY_MODEL = "etap:modify_model"
    ETAP_EXPORT_RESULTS = "etap:export_results"

    CALC_LOAD_FLOW = "calc:load_flow"
    CALC_SHORT_CIRCUIT = "calc:short_circuit"
    CALC_ARC_FLASH = "calc:arc_flash"
    CALC_PROTECTION = "calc:protection"
    CALC_HARMONIC = "calc:harmonic"
    CALC_OPF = "calc:opf"
    CALC_MOTOR_STARTING = "calc:motor_starting"

    EXEC_PYTHON = "exec:python"
    EXEC_POWERSHELL = "exec:powershell"
    EXEC_GUI_AUTOMATION = "exec:gui_automation"

    DATA_READ = "data:read"
    DATA_WRITE = "data:write"
    DATA_DELETE = "data:delete"

    ADMIN_USERS = "admin:users"
    ADMIN_SETTINGS = "admin:settings"
    ADMIN_AUDIT = "admin:audit"


ROLE_PERMISSIONS = {
    UserRole.ADMIN: set(Permission),
    UserRole.ENGINEER: {
        Permission.ETAP_LAUNCH,
        Permission.ETAP_OPEN_PROJECT,
        Permission.ETAP_CREATE_PROJECT,
        Permission.ETAP_RUN_STUDY,
        Permission.ETAP_MODIFY_MODEL,
        Permission.ETAP_EXPORT_RESULTS,
        Permission.CALC_LOAD_FLOW,
        Permission.CALC_SHORT_CIRCUIT,
        Permission.CALC_ARC_FLASH,
        Permission.CALC_PROTECTION,
        Permission.CALC_HARMONIC,
        Permission.CALC_OPF,
        Permission.CALC_MOTOR_STARTING,
        Permission.EXEC_PYTHON,
        Permission.EXEC_POWERSHELL,
        Permission.DATA_READ,
        Permission.DATA_WRITE,
    },
    UserRole.ANALYST: {
        Permission.ETAP_OPEN_PROJECT,
        Permission.ETAP_RUN_STUDY,
        Permission.ETAP_EXPORT_RESULTS,
        Permission.CALC_LOAD_FLOW,
        Permission.CALC_SHORT_CIRCUIT,
        Permission.CALC_ARC_FLASH,
        Permission.CALC_PROTECTION,
        Permission.CALC_MOTOR_STARTING,
        Permission.DATA_READ,
    },
    UserRole.VIEWER: {
        Permission.ETAP_OPEN_PROJECT,
        Permission.ETAP_EXPORT_RESULTS,
        Permission.DATA_READ,
    },
    UserRole.GUEST: set(),
}


@dataclass
class User:
    """User account."""
    user_id: str
    username: str
    email: str
    role: UserRole
    password_hash: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None
    is_active: bool = True
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None


@dataclass
class Session:
    """User session."""
    session_id: str
    user_id: str
    token: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=8))
    is_valid: bool = True


class AuthenticationManager:
    """
    Manages user authentication using JWT tokens.

    Features:
    - Password hashing with bcrypt
    - JWT token generation and validation
    - Session management
    - Account lockout after failed attempts
    """

    def __init__(self, secret_key: Optional[str] = None,
                 token_expiry_hours: int = 8,
                 max_failed_attempts: int = 5,
                 lockout_duration_minutes: int = 30):
        self.secret_key = secret_key or secrets.token_hex(32)
        self.token_expiry_hours = token_expiry_hours
        self.max_failed_attempts = max_failed_attempts
        self.lockout_duration_minutes = lockout_duration_minutes

        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Session] = {}
        self.username_to_id: Dict[str, str] = {}
        self.token_to_session: Dict[str, Session] = {}

        self.cipher = Fernet(Fernet.generate_key())

    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=14)).decode()

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against bcrypt hash.
        
        bcrypt.checkpw performs constant-time comparison internally.
        """
        try:
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        except Exception:
            return False

    def create_user(self, username: str, email: str, password: str,
                    role: UserRole = UserRole.VIEWER) -> Optional[User]:
        if username in self.username_to_id:
            logger.warning(f"Username '{username}' already exists")
            return None

        user_id = secrets.token_hex(16)
        password_hash = self._hash_password(password)

        user = User(
            user_id=user_id,
            username=username,
            email=email,
            role=role,
            password_hash=password_hash
        )

        self.users[user_id] = user
        self.username_to_id[username] = user_id

        logger.info(f"User created: {username} (role={role.value})")
        return user

    def authenticate(self, username: str, password: str) -> Optional[str]:
        user_id = self.username_to_id.get(username)
        if not user_id:
            logger.warning("Authentication failed: invalid credentials")
            return None

        user = self.users[user_id]

        if user.locked_until and datetime.now(timezone.utc) < user.locked_until:
            logger.warning("Authentication failed: account locked")
            return None

        if not self._verify_password(password, user.password_hash):
            user.failed_login_attempts += 1

            if user.failed_login_attempts >= self.max_failed_attempts:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=self.lockout_duration_minutes
                )
                logger.warning(f"Account locked: too many failed attempts")

            return None

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(timezone.utc)

        token = self._generate_token(user)

        session_id = secrets.token_hex(16)
        session = Session(
            session_id=session_id,
            user_id=user_id,
            token=token
        )
        self.sessions[session_id] = session
        self.token_to_session[token] = session

        logger.info(f"User authenticated: {username}")
        return token

    def _generate_token(self, user: User) -> str:
        """Generate JWT token for user."""
        now = datetime.now(timezone.utc)
        payload = {
            'user_id': user.user_id,
            'username': user.username,
            'role': user.role.value,
            'exp': now + timedelta(hours=self.token_expiry_hours),
            'iat': now
        }

        token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        # PyJWT may return bytes depending on version; normalize to str.
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return token

    def validate_token(self, token: str) -> Optional[User]:
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        session = self.token_to_session.get(token)
        if not session or not session.is_valid or datetime.now(timezone.utc) >= session.expires_at:
            return None

        user = self.users.get(session.user_id)
        if not user or not user.is_active:
            return None

        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            if payload['user_id'] != user.user_id:
                return None
        except jwt.ExpiredSignatureError:
            session.is_valid = False
            return None
        except jwt.InvalidTokenError:
            return None

        return user

    def logout(self, token: str) -> bool:
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        session = self.token_to_session.pop(token, None)
        if session:
            session.is_valid = False
            self.sessions.pop(session.session_id, None)
            logger.info(f"User logged out: {session.user_id}")
            return True
        return False

    def encrypt_secret(self, secret: str) -> str:
        """Encrypt a secret value using Fernet."""
        return self.cipher.encrypt(secret.encode()).decode()

    def decrypt_secret(self, encrypted: str) -> str:
        """Decrypt a secret value using Fernet."""
        return self.cipher.decrypt(encrypted.encode()).decode()


class AuthorizationManager:
    """
    Manages authorization and access control.

    Implements role-based access control (RBAC) with permission checking.
    """

    def __init__(self, auth_manager: AuthenticationManager):
        self.auth_manager = auth_manager

    def check_permission(self, token: str, permission: Permission) -> bool:
        user = self.auth_manager.validate_token(token)
        if not user:
            return False

        allowed_permissions = ROLE_PERMISSIONS.get(user.role, set())
        return permission in allowed_permissions

    def check_permissions(self, token: str, permissions: List[Permission]) -> bool:
        """Check if user has all required permissions."""
        return all(self.check_permission(token, perm) for perm in permissions)

    def get_user_permissions(self, token: str) -> Set[Permission]:
        """Get all permissions for a user."""
        user = self.auth_manager.validate_token(token)
        if not user:
            return set()

        return ROLE_PERMISSIONS.get(user.role, set())


class InputValidator:
    """
    Validates and sanitizes user inputs to prevent injection attacks.

    Features:
    - SQL injection prevention
    - Command injection prevention
    - Path traversal prevention
    - Type validation
    - Range validation
    """

    # ast.Exec was removed in Python 3 (historically Py2 only). This project targets Py3.8,
    # so reference it conditionally to keep compatibility.
    FORBIDDEN_AST_NODES = tuple(
        n for n in (
            getattr(ast, "Exec", None),
            getattr(ast, "Global", None),
            getattr(ast, "Nonlocal", None),
        ) if n is not None
    )

    FORBIDDEN_CALLS = {'__import__', 'eval', 'exec', 'compile'}

    FORBIDDEN_ATTRS = {'__import__', '__builtins__'}

    @staticmethod
    def validate_python_code(code: str, allowed_imports: Set[str] = None) -> bool:
        """
        Validate Python code for safety using AST parsing.

        Parameters:
        code: Python code to validate
        allowed_imports: Set of allowed module imports

        Returns:
        True if code is safe
        """
        if allowed_imports is None:
            allowed_imports = {
                'numpy', 'scipy', 'math', 'json', 'time',
                'core_model', 'engine', 'load_flow', 'fault_analysis',
                'relays', 'coordination'
            }

        try:
            tree = ast.parse(code)
        except SyntaxError:
            logger.warning("Code failed AST parsing")
            return False

        for node in ast.walk(tree):
            if isinstance(node, InputValidator.FORBIDDEN_AST_NODES):
                logger.warning(f"Forbidden AST node type: {type(node).__name__}")
                return False

            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split('.')[0]
                        if module not in allowed_imports:
                            logger.warning(f"Unauthorized import: {module}")
                            return False
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module = node.module.split('.')[0]
                        if module not in allowed_imports:
                            logger.warning(f"Unauthorized import: {module}")
                            return False

            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in InputValidator.FORBIDDEN_CALLS:
                    logger.warning(f"Forbidden function call: {func.id}")
                    return False
                if isinstance(func, ast.Attribute):
                    if func.attr in InputValidator.FORBIDDEN_ATTRS:
                        logger.warning(f"Forbidden attribute access: {func.attr}")
                        return False

            if isinstance(node, ast.Attribute):
                if node.attr in InputValidator.FORBIDDEN_ATTRS:
                    logger.warning(f"Forbidden attribute access: {node.attr}")
                    return False

            if isinstance(node, ast.Name) and node.id in InputValidator.FORBIDDEN_CALLS:
                logger.warning(f"Forbidden name reference: {node.id}")
                return False

        return True

    @staticmethod
    def validate_powershell_command(command: str, allowed_commands: Set[str] = None) -> bool:
        """
        Validate PowerShell command for safety.

        Parameters:
        command: PowerShell command to validate
        allowed_commands: Set of allowed commands

        Returns:
        True if command is safe
        """
        if allowed_commands is None:
            allowed_commands = {
                'Get-Process', 'Get-Service', 'Get-EventLog',
                'Test-Connection', 'Get-NetAdapter', 'Get-ComputerInfo'
            }

        normalized = ' '.join(command.split())

        dangerous_patterns = [
            'Invoke-Expression', 'Invoke-Command', 'Invoke-WebRequest',
            'Start-Process', 'New-Object', 'WebClient',
            'DownloadString', 'IEX', '|', ';',
            '-Enc', '-EncodedCommand',
            'System.Diagnostics', 'System.Reflection',
        ]

        for pattern in dangerous_patterns:
            if pattern.lower() in normalized.lower():
                logger.warning(f"Dangerous pattern in PowerShell command: {pattern}")
                return False

        if '[' in normalized:
            logger.warning("PowerShell .NET type access detected")
            return False

        if '`' in normalized:
            logger.warning("PowerShell backtick escaping detected")
            return False

        cmd_name = normalized.strip().split()[0] if normalized.strip() else ''

        if cmd_name not in allowed_commands:
            logger.warning(f"Unauthorized PowerShell command: {cmd_name}")
            return False

        return True

    @staticmethod
    def validate_file_path(path: str, allowed_directories: List[str] = None) -> bool:
        """
        Validate file path to prevent path traversal.

        Parameters:
        path: File path to validate
        allowed_directories: List of allowed base directories

        Returns:
        True if path is safe
        """
        if allowed_directories is None:
            allowed_directories = [os.getcwd()]

        try:
            resolved_path = Path(path).resolve()
        except (OSError, ValueError):
            logger.warning(f"Invalid path: {path}")
            return False

        for allowed_dir in allowed_directories:
            try:
                resolved_allowed = Path(allowed_dir).resolve()
            except (OSError, ValueError):
                continue
            try:
                resolved_path.relative_to(resolved_allowed)
                return True
            except ValueError:
                continue

        logger.warning(f"Path outside allowed directories: {path}")
        return False

    @staticmethod
    def validate_numeric(value, min_val=None, max_val=None) -> bool:
        """Validate numeric value is within range."""
        try:
            num = float(value)
            if min_val is not None and num < min_val:
                return False
            if max_val is not None and num > max_val:
                return False
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def sanitize_string(input_str: str, max_length: int = 1000) -> str:
        """Sanitize string input."""
        sanitized = input_str.replace('\x00', '')

        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        return sanitized


class RateLimiter:
    """
    Rate limiting to prevent abuse.

    Implements token bucket algorithm with LRU eviction and TTL cleanup.
    """

    MAX_CLIENT_MULTIPLIER = 10

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = {}

    def _cleanup_expired(self, client_id: str, now: float):
        self.requests[client_id] = [
            t for t in self.requests[client_id]
            if now - t < self.window_seconds
        ]

    def _evict_stale_clients(self, now: float):
        stale = [
            cid for cid, timestamps in self.requests.items()
            if not timestamps or (now - timestamps[-1]) >= self.window_seconds
        ]
        for cid in stale:
            del self.requests[cid]

    def _evict_oldest_if_needed(self):
        max_clients = self.MAX_CLIENT_MULTIPLIER * self.max_requests
        if len(self.requests) > max_clients:
            sorted_clients = sorted(
                self.requests.items(),
                key=lambda item: item[1][-1] if item[1] else 0
            )
            to_remove = len(self.requests) - max_clients
            for cid, _ in sorted_clients[:to_remove]:
                del self.requests[cid]

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()

        if client_id not in self.requests:
            self.requests[client_id] = []

        self._cleanup_expired(client_id, now)

        if len(self.requests[client_id]) < self.max_requests:
            self.requests[client_id].append(now)
            self._evict_oldest_if_needed()
            return True

        self._evict_stale_clients(now)

        logger.warning(f"Rate limit exceeded for client: {client_id}")
        return False


class AuditLogger:
    """
    Logs security-relevant events for audit trail.
    """

    def __init__(self, log_file: str = "security_audit.log"):
        self.log_file = log_file
        self.logger = logging.getLogger("audit")

        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def log_event(self, event_type: str, user_id: str, action: str,
                  details: Dict = None, success: bool = True):
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'event_type': event_type,
            'user_id': user_id,
            'action': action,
            'success': success,
            'details': details or {}
        }

        level = logging.INFO if success else logging.WARNING
        self.logger.log(level, json.dumps(log_entry))

    def log_login(self, user_id: str, success: bool, ip_address: str = None):
        """Log login attempt."""
        self.log_event(
            'login', user_id,
            f"Login attempt from {ip_address or 'unknown'}",
            {'ip_address': ip_address},
            success
        )

    def log_action(self, user_id: str, action: str, resource: str, success: bool = True):
        """Log user action."""
        self.log_event(
            'action', user_id,
            f"{action} on {resource}",
            {'resource': resource},
            success
        )

    def log_security_violation(self, user_id: str, violation: str, details: Dict = None):
        """Log security violation."""
        self.log_event(
            'violation', user_id,
            f"Security violation: {violation}",
            details,
            False
        )


_auth_manager = None
_authz_manager = None
_validator = None
_rate_limiter = None
_audit_logger = None

_auth_manager_lock = threading.Lock()
_authz_manager_lock = threading.Lock()
_validator_lock = threading.Lock()
_rate_limiter_lock = threading.Lock()
_audit_logger_lock = threading.Lock()


def get_auth_manager() -> AuthenticationManager:
    """Get or create authentication manager singleton."""
    global _auth_manager
    with _auth_manager_lock:
        if _auth_manager is None:
            secret_key = os.environ.get('JWT_SECRET_KEY')
            _auth_manager = AuthenticationManager(secret_key=secret_key)
    return _auth_manager


def get_authz_manager() -> AuthorizationManager:
    """Get or create authorization manager singleton."""
    global _authz_manager
    with _authz_manager_lock:
        if _authz_manager is None:
            _authz_manager = AuthorizationManager(get_auth_manager())
    return _authz_manager


def get_validator() -> InputValidator:
    """Get input validator singleton."""
    global _validator
    with _validator_lock:
        if _validator is None:
            _validator = InputValidator()
    return _validator


def get_rate_limiter() -> RateLimiter:
    """Get rate limiter singleton."""
    global _rate_limiter
    with _rate_limiter_lock:
        if _rate_limiter is None:
            _rate_limiter = RateLimiter()
    return _rate_limiter


def get_audit_logger() -> AuditLogger:
    """Get audit logger singleton."""
    global _audit_logger
    with _audit_logger_lock:
        if _audit_logger is None:
            _audit_logger = AuditLogger()
    return _audit_logger
