"""
ETAP Error Recovery
===================
Provides ETAP-specific error classification and recovery strategies
for COM automation failures, study execution errors, and project I/O issues.
Integrates with engine.resilience for RetryHandler and CircuitBreaker
when available, with standalone fallback implementations.
"""

import sys
import os
import time
import logging
import subprocess
from enum import Enum
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

if sys.platform == 'win32':
    try:
        import win32com.client
        import pythoncom
        WIN32_AVAILABLE = True
    except ImportError:
        WIN32_AVAILABLE = False
else:
    WIN32_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    from engine.resilience import RetryHandler, CircuitBreaker, CircuitBreakerOpenError
    HAS_RESILIENCE = True
except ImportError:
    HAS_RESILIENCE = False

ETAP_PROCESS_NAME = "ETAP.exe"
ETAP_COM_PROG_ID = "ETAP.Application"


class ErrorCategory(Enum):
    COM_CONNECTION_LOST = "COM_CONNECTION_LOST"
    STUDY_EXECUTION_FAILED = "STUDY_EXECUTION_FAILED"
    PROJECT_IO_ERROR = "PROJECT_IO_ERROR"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    LICENSE_ERROR = "LICENSE_ERROR"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    UNKNOWN = "UNKNOWN"


@dataclass
class ErrorDiagnosis:
    category: ErrorCategory
    message: str
    suggestion: str
    recoverable: bool
    requires_restart: bool = False


@dataclass
class RecoveryAttempt:
    success: bool
    action: str
    duration: float
    error: Optional[str] = None


class ETAPErrorRecovery:
    """ETAP-specific error recovery with retry and circuit breaker patterns.

    Parameters
    ----------
    max_retries : int
        Maximum retry attempts for recoverable operations (default 3).
    restart_on_crash : bool
        Auto-restart ETAP when COM connection is lost (default True).
    """

    def __init__(self, max_retries: int = 3, restart_on_crash: bool = True) -> None:
        self.max_retries = max_retries
        self.restart_on_crash = restart_on_crash
        self._recovery_count = 0
        self._successful_recoveries = 0
        self._restart_attempts = 0

        if HAS_RESILIENCE:
            self._retry_handler = RetryHandler(max_retries=max_retries)
            self._com_breaker = CircuitBreaker(
                name="etap-com", failure_threshold=3, recovery_timeout=60.0, half_open_max_calls=1,
            )
        else:
            self._retry_handler = None
            self._com_breaker = None

    def recover_from_com_error(self, error: Exception) -> RecoveryAttempt:
        """Recover from ETAP COM connection errors via circuit breaker and auto-restart."""
        start = time.monotonic()
        diag = self.get_error_diagnosis(error)

        if diag.category != ErrorCategory.COM_CONNECTION_LOST:
            return RecoveryAttempt(False, "skip", time.monotonic() - start,
                                   f"Not a COM error: {diag.category.value}")

        logger.warning("Attempting COM recovery: %s", diag.message)

        if self._com_breaker is not None:
            try:
                if self._com_breaker.call(self._ping_etap_com):
                    self._recovery_count += 1; self._successful_recoveries += 1
                    return RecoveryAttempt(True, "circuit_breaker", time.monotonic() - start)
            except CircuitBreakerOpenError:
                logger.info("COM circuit breaker is OPEN; attempting restart.")
            except Exception as cb_err:
                # Non-trip errors during the circuit-breaker probe (e.g. transient
                # RPC faults) should not be silently dropped.  Log and fall through
                # to the auto-restart path so the caller still gets a decision.
                logger.warning("Circuit breaker probe raised %s: %s",
                               type(cb_err).__name__, cb_err)

        if self.restart_on_crash and self.auto_restart_etap():
            self._recovery_count += 1; self._successful_recoveries += 1
            return RecoveryAttempt(True, "auto_restart", time.monotonic() - start)

        return RecoveryAttempt(False, "failed", time.monotonic() - start,
                               "No recovery method succeeded")

    def recover_from_study_error(self, error: Exception, study_type: str) -> RecoveryAttempt:
        """Recover from study execution errors by parameter checking and retry."""
        start = time.monotonic()
        diag = self.get_error_diagnosis(error)

        if diag.category == ErrorCategory.INVALID_PARAMETER:
            return RecoveryAttempt(False, "invalid_param", time.monotonic() - start,
                                   f"Study {study_type}: {diag.message}")
        if diag.category == ErrorCategory.LICENSE_ERROR:
            return RecoveryAttempt(False, "license_error", time.monotonic() - start,
                                   f"ETAP license not available for {study_type}")
        if diag.category == ErrorCategory.COM_CONNECTION_LOST:
            cr = self.recover_from_com_error(error)
            if cr.success:
                self._recovery_count += 1; self._successful_recoveries += 1
                return RecoveryAttempt(True, f"com_recovery:{cr.action}", time.monotonic() - start)
            return cr

        if self._retry_handler is not None:
            try:
                self._retry_handler.execute(self._raise_study_retryable, error, study_type,
                                            retryable_exceptions=(RuntimeError, ConnectionError, TimeoutError))
                self._recovery_count += 1; self._successful_recoveries += 1
                return RecoveryAttempt(True, "retry_ok", time.monotonic() - start)
            except Exception as e:
                return RecoveryAttempt(False, "retry_exhausted", time.monotonic() - start, str(e))

        return RecoveryAttempt(False, "no_retry", time.monotonic() - start,
                               "RetryHandler not available")

    def recover_from_project_error(self, error: Exception, project_path: str) -> RecoveryAttempt:
        """Recover from project I/O errors by validating the file and COM state."""
        start = time.monotonic()
        diag = self.get_error_diagnosis(error)

        if diag.category != ErrorCategory.PROJECT_IO_ERROR:
            return RecoveryAttempt(False, "not_project_error", time.monotonic() - start,
                                   f"Unexpected category: {diag.category.value}")

        if not os.path.exists(project_path):
            return RecoveryAttempt(False, "file_not_found", time.monotonic() - start,
                                   f"File not found: {project_path}")
        if not os.access(project_path, os.R_OK):
            return RecoveryAttempt(False, "file_not_readable", time.monotonic() - start,
                                   f"File not readable: {project_path}")

        if self.is_etap_responsive():
            self._recovery_count += 1; self._successful_recoveries += 1
            return RecoveryAttempt(True, "file_valid", time.monotonic() - start)

        cr = self.recover_from_com_error(error)
        if cr.success:
            self._recovery_count += 1; self._successful_recoveries += 1
            return RecoveryAttempt(True, f"com_restored:{cr.action}", time.monotonic() - start)
        return cr

    def auto_restart_etap(self) -> bool:
        """Kill ETAP processes and relaunch via COM Dispatch."""
        logger.info("Attempting automatic ETAP restart...")
        self._restart_attempts += 1
        self._kill_etap_processes()
        time.sleep(5.0)

        if not WIN32_AVAILABLE:
            return False
        try:
            pythoncom.CoInitialize()
            try:
                app = win32com.client.Dispatch(ETAP_COM_PROG_ID)
                if hasattr(app, 'Visible'):
                    app.Visible = True
                if hasattr(app, 'Timeout'):
                    app.Timeout = 300000
                logger.info("ETAP restarted successfully.")
                return True
            finally:
                pythoncom.CoUninitialize()
        except Exception as e:
            logger.error("Failed to restart ETAP: %s", e)
        return False

    def is_etap_responsive(self) -> bool:
        """Ping ETAP via COM to verify responsiveness."""
        if not WIN32_AVAILABLE:
            return False
        for attempt in range(3):
            try:
                pythoncom.CoInitialize()
                try:
                    _ = win32com.client.GetActiveObject(ETAP_COM_PROG_ID).Visible
                    return True
                finally:
                    pythoncom.CoUninitialize()
            except pythoncom.com_error:
                if attempt < 2:
                    time.sleep(1.0)
                continue
            except Exception:
                return False
        return False

    def get_error_diagnosis(self, error: Exception) -> ErrorDiagnosis:
        """Classify an ETAP error by analysing the exception type and message."""
        msg = str(error).lower()

        if isinstance(error, pythoncom.com_error) if 'pythoncom' in sys.modules else False:
            return ErrorDiagnosis(ErrorCategory.COM_CONNECTION_LOST,
                "ETAP COM interface disconnected or process crashed.",
                "Restart ETAP and re-establish the COM connection.", True, True)

        if any(k in msg for k in ['com_error', 'rpc', 'server', 'disconnected', '0x800706ba', '0x80010108']):
            return ErrorDiagnosis(ErrorCategory.COM_CONNECTION_LOST,
                "ETAP COM interface disconnected or process crashed.",
                "Restart ETAP and re-establish the COM connection.", True, True)

        if any(k in msg for k in ['study', 'calculation', 'converge', 'diverg', 'iteration']):
            return ErrorDiagnosis(ErrorCategory.STUDY_EXECUTION_FAILED,
                f"Study execution failed: {error}",
                "Verify study parameters and project configuration, then retry.", True)

        if any(k in msg for k in ['file', 'project', 'open', 'save', 'edb', 'permission', 'access']):
            return ErrorDiagnosis(ErrorCategory.PROJECT_IO_ERROR,
                f"Project I/O error: {error}",
                "Check file permissions, path validity, and disk space.", False)

        if any(k in msg for k in ['license', 'activation', 'expir', 'dongle']):
            return ErrorDiagnosis(ErrorCategory.LICENSE_ERROR,
                f"ETAP license error: {error}",
                "Verify a valid ETAP license is installed and activated.", False)

        if any(k in msg for k in ['version', 'compatible', 'incompatible', 'not supported']):
            return ErrorDiagnosis(ErrorCategory.VERSION_MISMATCH,
                f"Incompatible ETAP version: {error}",
                "Install a supported ETAP version (12.0 or later).", False)

        if any(k in msg for k in ['parameter', 'invalid', 'out of range', 'validation', 'argument']):
            return ErrorDiagnosis(ErrorCategory.INVALID_PARAMETER,
                f"Invalid parameter: {error}",
                "Review parameter values against ETAP requirements.", True)

        return ErrorDiagnosis(ErrorCategory.UNKNOWN, str(error),
                              "Check application logs for detailed context.", False)

    @property
    def recovery_count(self) -> int:
        return self._recovery_count

    @property
    def successful_recoveries(self) -> int:
        return self._successful_recoveries

    @property
    def restart_attempts(self) -> int:
        return self._restart_attempts

    @property
    def success_rate(self) -> float:
        if self._recovery_count == 0:
            return 0.0
        return self._successful_recoveries / self._recovery_count

    def _ping_etap_com(self) -> bool:
        if not WIN32_AVAILABLE:
            return False
        pythoncom.CoInitialize()
        try:
            _ = win32com.client.GetActiveObject(ETAP_COM_PROG_ID).Version
            return True
        except (pythoncom.com_error, AttributeError):
            return False
        finally:
            pythoncom.CoUninitialize()

    @staticmethod
    def _raise_study_retryable(error: Exception, study_type: str) -> None:
        raise RuntimeError(f"Study {study_type} failed after retry: {error}")

    def _kill_etap_processes(self) -> int:
        killed = 0
        if PSUTIL_AVAILABLE:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == ETAP_PROCESS_NAME.lower():
                        proc.kill(); killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        elif WIN32_AVAILABLE:
            try:
                r = subprocess.run(["taskkill", "/F", "/IM", ETAP_PROCESS_NAME],
                                   capture_output=True, text=True, timeout=10)
                if r.returncode == 0:
                    killed = len([l for l in r.stdout.splitlines() if l.strip()])
            except subprocess.TimeoutExpired:
                logger.warning("taskkill timed out while killing %s", ETAP_PROCESS_NAME)
            except FileNotFoundError:
                logger.warning("taskkill executable not found on PATH; cannot kill %s",
                               ETAP_PROCESS_NAME)
            except OSError as os_err:
                logger.warning("OS error while running taskkill: %s", os_err)
        if killed:
            logger.info("Killed %d ETAP process(es).", killed)
        return killed
