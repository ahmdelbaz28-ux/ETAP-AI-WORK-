"""
ETAP Integration Package
========================
Provides ETAP COM automation, provider abstraction, worker service,
error recovery, and compatibility checking for the ETAP AI platform.
"""

from etap_integration.etap_com import ETAPAutomation, ETAPProject, ETAPResult, ETAPStudyType
from etap_integration.etap_provider import (
    IEtapProvider,
    LocalEtapProvider,
    RemoteEtapProvider,
    MockEtapProvider,
    NullEtapProvider,
    get_etap_provider,
    ETAPStudyType as ProviderStudyType,
    ETAPResult as ProviderResult,
)
from etap_integration.etap_error_recovery import ETAPErrorRecovery, ErrorCategory, ErrorDiagnosis, RecoveryAttempt
from etap_integration.etap_compatibility import ETAPCompatibilityChecker, CompatibilityReport, CheckResult

__all__ = [
    # COM automation
    "ETAPAutomation",
    "ETAPProject",
    "ETAPResult",
    "ETAPStudyType",
    # Provider abstraction
    "IEtapProvider",
    "LocalEtapProvider",
    "RemoteEtapProvider",
    "MockEtapProvider",
    "NullEtapProvider",
    "get_etap_provider",
    "ProviderStudyType",
    "ProviderResult",
    # Error recovery
    "ETAPErrorRecovery",
    "ErrorCategory",
    "ErrorDiagnosis",
    "RecoveryAttempt",
    # Compatibility
    "ETAPCompatibilityChecker",
    "CompatibilityReport",
    "CheckResult",
]
