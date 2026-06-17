"""
ETAP Integration Package
========================
Provides ETAP COM automation, provider abstraction, worker service,
error recovery, compatibility checking, and sync engine for the ETAP AI platform.
"""

import sys as _sys

# Lazy imports to support cross-platform loading.
# Windows-only modules (winreg, pywin32) are only imported on win32.

_ETAPAutomation = None
_ETAPProject = None
_ETAPResult = None
_ETAPStudyType = None

_IEtapProvider = None
_LocalEtapProvider = None
_RemoteEtapProvider = None
_MockEtapProvider = None
_NullEtapProvider = None
_get_etap_provider = None

_ETAPErrorRecovery = None
_ErrorCategory = None
_ErrorDiagnosis = None
_RecoveryAttempt = None

_ETAPCompatibilityChecker = None
_CompatibilityReport = None
_CheckResult = None

_ETAPSyncEngine = None


def __getattr__(name):
    if name in ("ETAPAutomation", "ETAPProject", "ETAPResult", "ETAPStudyType"):
        global _ETAPAutomation, _ETAPProject, _ETAPResult, _ETAPStudyType
        if _ETAPAutomation is None:
            from etap_integration.etap_com import ETAPAutomation as _ETAPAutomation
            from etap_integration.etap_com import ETAPProject as _ETAPProject
            from etap_integration.etap_com import ETAPResult as _ETAPResult
            from etap_integration.etap_com import ETAPStudyType as _ETAPStudyType
        mapping = {
            "ETAPAutomation": _ETAPAutomation,
            "ETAPProject": _ETAPProject,
            "ETAPResult": _ETAPResult,
            "ETAPStudyType": _ETAPStudyType,
        }
        return mapping[name]
    if name in ("IEtapProvider", "LocalEtapProvider", "RemoteEtapProvider",
                "MockEtapProvider", "NullEtapProvider", "get_etap_provider",
                "ProviderStudyType", "ProviderResult"):
        global _IEtapProvider, _LocalEtapProvider, _RemoteEtapProvider
        global _MockEtapProvider, _NullEtapProvider, _get_etap_provider
        if _IEtapProvider is None:
            from etap_integration.etap_provider import IEtapProvider as _IEtapProvider
            from etap_integration.etap_provider import LocalEtapProvider as _LocalEtapProvider
            from etap_integration.etap_provider import MockEtapProvider as _MockEtapProvider
            from etap_integration.etap_provider import NullEtapProvider as _NullEtapProvider
            from etap_integration.etap_provider import RemoteEtapProvider as _RemoteEtapProvider
            from etap_integration.etap_provider import get_etap_provider as _get_etap_provider
        mapping = {
            "IEtapProvider": _IEtapProvider,
            "LocalEtapProvider": _LocalEtapProvider,
            "RemoteEtapProvider": _RemoteEtapProvider,
            "MockEtapProvider": _MockEtapProvider,
            "NullEtapProvider": _NullEtapProvider,
            "get_etap_provider": _get_etap_provider,
            "ProviderStudyType": _ETAPStudyType,
            "ProviderResult": _ETAPResult,
        }
        return mapping[name]
    if name in ("ETAPErrorRecovery", "ErrorCategory", "ErrorDiagnosis", "RecoveryAttempt"):
        global _ETAPErrorRecovery, _ErrorCategory, _ErrorDiagnosis, _RecoveryAttempt
        if _ETAPErrorRecovery is None:
            from etap_integration.etap_error_recovery import ErrorCategory as _ErrorCategory
            from etap_integration.etap_error_recovery import ErrorDiagnosis as _ErrorDiagnosis
            from etap_integration.etap_error_recovery import ETAPErrorRecovery as _ETAPErrorRecovery
            from etap_integration.etap_error_recovery import RecoveryAttempt as _RecoveryAttempt
        mapping = {
            "ETAPErrorRecovery": _ETAPErrorRecovery,
            "ErrorCategory": _ErrorCategory,
            "ErrorDiagnosis": _ErrorDiagnosis,
            "RecoveryAttempt": _RecoveryAttempt,
        }
        return mapping[name]
    if name in ("ETAPCompatibilityChecker", "CompatibilityReport", "CheckResult"):
        global _ETAPCompatibilityChecker, _CompatibilityReport, _CheckResult
        if _ETAPCompatibilityChecker is None:
            from etap_integration.etap_compatibility import CheckResult as _CheckResult
            from etap_integration.etap_compatibility import CompatibilityReport as _CompatibilityReport
            from etap_integration.etap_compatibility import ETAPCompatibilityChecker as _ETAPCompatibilityChecker
        mapping = {
            "ETAPCompatibilityChecker": _ETAPCompatibilityChecker,
            "CompatibilityReport": _CompatibilityReport,
            "CheckResult": _CheckResult,
        }
        return mapping[name]
    if name == "ETAPSyncEngine":
        global _ETAPSyncEngine
        if _ETAPSyncEngine is None:
            from etap_integration.sync_engine import ETAPSyncEngine as _ETAPSyncEngine
        return _ETAPSyncEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ETAPAutomation",
    "ETAPProject",
    "ETAPResult",
    "ETAPStudyType",
    "IEtapProvider",
    "LocalEtapProvider",
    "RemoteEtapProvider",
    "MockEtapProvider",
    "NullEtapProvider",
    "get_etap_provider",
    "ProviderStudyType",
    "ProviderResult",
    "ETAPErrorRecovery",
    "ErrorCategory",
    "ErrorDiagnosis",
    "RecoveryAttempt",
    "ETAPCompatibilityChecker",
    "CompatibilityReport",
    "CheckResult",
    "ETAPSyncEngine",
]
