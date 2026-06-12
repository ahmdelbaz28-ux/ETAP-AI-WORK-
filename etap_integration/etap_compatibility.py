"""
ETAP Compatibility Checker
==========================
Verifies that the runtime environment meets ETAP software requirements,
including ETAP version, Windows version, .NET Framework, and availability
of required COM modules and Python dependencies.
"""

import sys, platform, logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

WIN32_AVAILABLE = False
if sys.platform == 'win32':
    try:
        import winreg  # noqa: F401
        import win32com.client, pythoncom
        WIN32_AVAILABLE = True
    except ImportError:
        WIN32_AVAILABLE = False

SUPPORTED_ETAP_VERSIONS: List[str] = [
    "12.0.0", "12.5.0", "12.6.0", "14.0.0", "14.1.0",
    "15.0.0", "16.0.0", "16.1.0", "20.0.0", "20.5.0", "21.0.0", "22.0.0",
]
MIN_ETAP_VERSION = "12.0.0"

REQUIRED_PACKAGES = ["pywin32", "psutil", "pyyaml", "numpy"]
OPTIONAL_PACKAGES = ["requests", "pydantic"]

COM_MODULES = [
    "LoadFlow", "ShortCircuit", "ArcFlash", "MotorAcceleration",
    "TransientStability", "HarmonicAnalysis", "OptimalPowerFlow",
    "ProtectionCoordination", "CableAmpacity", "GroundGrid", "Reliability",
]


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str
    severity: str = "info"


@dataclass
class CompatibilityReport:
    etap_version: Optional[str]
    version_supported: bool
    windows_ok: bool
    dotnet_ok: bool
    dependencies_ok: bool
    com_modules_available: List[str]
    com_modules_missing: List[str]
    checks: List[CheckResult] = field(default_factory=list)
    overall_pass: bool = False


def _parse_version(v: str) -> Tuple[int, ...]:
    try:
        return tuple(int(p) for p in v.strip().split("."))
    except (ValueError, AttributeError):
        return (0,)


class ETAPCompatibilityChecker:
    """Verifies ETAP runtime environment compatibility.

    Parameters
    ----------
    etap_prog_id : str
        COM ProgID for the ETAP application (default 'ETAP.Application').
    """

    def __init__(self, etap_prog_id: str = "ETAP.Application") -> None:
        self._etap_prog_id = etap_prog_id
        self._cached_version: Optional[str] = None
        self._cached_com_modules: Optional[Dict[str, bool]] = None

    def check_version(self) -> Optional[str]:
        """Detect the installed ETAP version via COM."""
        if self._cached_version is not None:
            return self._cached_version
        if not WIN32_AVAILABLE:
            return None
        try:
            pythoncom.CoInitialize()
            try:
                app = win32com.client.GetActiveObject(self._etap_prog_id)
                raw = getattr(app, 'Version', None) or getattr(app, 'VersionNumber', None)
                if raw is not None:
                    self._cached_version = str(raw).strip()
                    return self._cached_version
                return None
            finally:
                pythoncom.CoUninitialize()
        except Exception as e:
            logger.debug("Could not get ETAP version: %s", e)
            return None

    def is_version_supported(self, version: Optional[str] = None) -> bool:
        """Check whether the given (or installed) version is supported."""
        if version is None:
            version = self.check_version()
        if version is None:
            return False
        pv = _parse_version(version)
        if pv >= _parse_version(MIN_ETAP_VERSION):
            return True
        return version in SUPPORTED_ETAP_VERSIONS or any(
            version.startswith(v) for v in SUPPORTED_ETAP_VERSIONS
        )

    def get_supported_versions(self) -> List[str]:
        return list(SUPPORTED_ETAP_VERSIONS)

    def check_module_availability(self, module_name: str) -> bool:
        """Check if a COM module is accessible from the active ETAP project."""
        if not WIN32_AVAILABLE:
            return False
        if self._cached_com_modules is not None and module_name in self._cached_com_modules:
            return self._cached_com_modules[module_name]
        try:
            pythoncom.CoInitialize()
            try:
                app = win32com.client.GetActiveObject(self._etap_prog_id)
                proj = getattr(app, 'ActiveProject', None)
                if proj is None:
                    return False
                avail = getattr(proj, module_name, None) is not None
                (self._cached_com_modules or {}).update({module_name: avail})
                if self._cached_com_modules is None:
                    self._cached_com_modules = {module_name: avail}
                return avail
            finally:
                pythoncom.CoUninitialize()
        except Exception as e:
            logger.debug("Module check failed for '%s': %s", module_name, e)
            return False

    def check_windows_version(self) -> Tuple[bool, str]:
        """Verify Windows meets ETAP requirements (10+ x64)."""
        if sys.platform != 'win32':
            return False, "Not running on Windows."
        try:
            major, minor, build, _, _ = platform.win32_ver()
            is_64 = platform.machine().endswith('64')
            if int(major) < 10:
                return False, f"Windows {major}.{minor} (build {build}) is too old. Win10+ required."
            if not is_64:
                return False, "ETAP requires 64-bit Windows (x64)."
            return True, f"Windows {major}.{minor} (build {build}) x64 - OK."
        except Exception as e:
            return False, f"Could not determine Windows version: {e}"

    def check_dependencies(self) -> Dict[str, bool]:
        """Verify required and optional Python packages."""
        return {pkg: self._is_package_available(pkg)
                for pkg in REQUIRED_PACKAGES + OPTIONAL_PACKAGES}

    def check_dotnet_version(self) -> Tuple[bool, str]:
        """Check .NET Framework 4.8+ via registry."""
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full")
            release = winreg.QueryValueEx(key, "Release")[0]
            winreg.CloseKey(key)
            names = {528040: "4.8", 528049: "4.8", 528209: "4.8", 533320: "4.8.1", 533325: "4.8.1"}
            detected = names.get(release, f"4.x (DWORD: {release})")
            if release >= 528040:
                return True, f".NET Framework {detected} - OK."
            return False, f".NET Framework {detected} is too old. 4.8+ required."
        except FileNotFoundError:
            return False, ".NET Framework v4 or later is not installed."
        except Exception as e:
            return False, f"Could not check .NET Framework: {e}"

    def run_compatibility_tests(self) -> List[CheckResult]:
        """Run all compatibility checks and return results."""
        checks: List[CheckResult] = []

        version = self.check_version()
        if version:
            supported = self.is_version_supported(version)
            checks.append(CheckResult("ETAP Version", supported,
                          f"Installed: {version}, Supported: {supported}",
                          "error" if not supported else "info"))
        else:
            checks.append(CheckResult("ETAP Version", False,
                          "Could not detect ETAP version. Is ETAP installed?", "error"))

        w_ok, w_msg = self.check_windows_version()
        checks.append(CheckResult("Windows Version", w_ok, w_msg,
                      "error" if not w_ok else "info"))

        d_ok, d_msg = self.check_dotnet_version()
        checks.append(CheckResult(".NET Framework", d_ok, d_msg,
                      "error" if not d_ok else "info"))

        for pkg, avail in self.check_dependencies().items():
            required = pkg in REQUIRED_PACKAGES
            sev = "error" if (required and not avail) else "warning" if not avail else "info"
            checks.append(CheckResult(f"Package: {pkg}", avail,
                          f"{'Required' if required else 'Optional'}: {'OK' if avail else 'missing'}", sev))

        for mod in COM_MODULES:
            avail = self.check_module_availability(mod)
            checks.append(CheckResult(f"COM Module: {mod}", avail,
                          "Available" if avail else "Not available",
                          "warning" if not avail else "info"))

        return checks

    def get_compatibility_report(self) -> CompatibilityReport:
        """Generate a detailed compatibility report with overall verdict."""
        checks = self.run_compatibility_tests()
        version = self.check_version()
        supported = self.is_version_supported(version) if version else False

        windows_ok = any(c.passed for c in checks if c.name == "Windows Version")
        dotnet_ok = any(c.passed for c in checks if c.name == ".NET Framework")
        deps_ok = all(c.passed for c in checks if c.name.startswith("Package:") and c.severity == "error")

        com_avail = [c.name.replace("COM Module: ", "") for c in checks
                     if c.name.startswith("COM Module:") and c.passed]
        com_miss = [c.name.replace("COM Module: ", "") for c in checks
                    if c.name.startswith("COM Module:") and not c.passed]

        return CompatibilityReport(
            etap_version=version,
            version_supported=supported,
            windows_ok=windows_ok,
            dotnet_ok=dotnet_ok,
            dependencies_ok=deps_ok,
            com_modules_available=com_avail,
            com_modules_missing=com_miss,
            checks=checks,
            overall_pass=supported and windows_ok and dotnet_ok and deps_ok,
        )

    @staticmethod
    def _is_package_available(name: str) -> bool:
        try:
            __import__(name.replace("-", "_"))
            return True
        except ImportError:
            try:
                __import__(name)
                return True
            except ImportError:
                return False
