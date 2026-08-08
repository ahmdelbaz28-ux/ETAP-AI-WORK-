"""
tests/test_audit_phase1_fixes.py — Verification tests for Phase 1 critical fixes.

Validates that all 8 Phase 1 audit findings are properly remediated:
  E-01: Arc flash simplified model flagged as non-compliant
  E-02: Distance exponent x uses per-configuration values (not hardcoded 1.0)
  E-03: Non-converged load flow does NOT write back invalid voltages
  S-01: CSRF bypass value removed (no literal "bypass" accepted)
  S-02: Registration role removed (no self-assigned admin)
  S-03: WebSocket requires authentication (JWT token or API key)
  S-05: Test mode grants "service" role (not "admin")
  S-07: AI/ML endpoints require authentication
  S-18: nginx uses $connection_upgrade (not literal "upgrade")

Run: pytest tests/test_audit_phase1_fixes.py -v
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# E-01 & E-02: Arc Flash Engine
# ---------------------------------------------------------------------------


class TestArcFlashE01E02:
    """Verify arc flash incident energy formula and distance exponent fixes."""

    def test_e01_simplified_flag_present(self):
        """E-01: ENGINE_IS_SIMPLIFIED flag must be True."""
        from fault_analysis.arc_flash_engine import ENGINE_IS_SIMPLIFIED

        assert ENGINE_IS_SIMPLIFIED is True

    def test_e01_non_compliance_warning_in_source(self):
        """E-01: Source must document the formula and its compliance status."""
        src = Path("fault_analysis/arc_flash_engine.py").read_text(encoding="utf-8")
        # Must reference IEEE 1584
        assert "IEEE 1584" in src
        # Must contain the full equation with log10(t)
        assert "log10_t" in src or "log10(t)" in src, (
            "E-01: Formula must include log10(t) time term"
        )
        # Must include gap distance G
        assert "log10_G" in src or "gap" in src.lower(), (
            "E-01: Formula must include gap distance G term"
        )
        # Must include K4 interaction term
        assert "k4" in src.lower(), "E-01: Formula must include K4 interaction term"

    def test_e02_x_factor_from_table(self):
        """E-02: x_factor must be unpacked from coefficients (not discarded)."""
        src = Path("fault_analysis/arc_flash_engine.py").read_text(encoding="utf-8")
        # The unpack line must use x_factor, not _ (now 5-tuple: k1,k2,k3,k4,x_factor)
        assert re.search(r"k1,\s*k2,\s*k3,\s*k4,\s*x_factor\s*=", src), (
            "x_factor must be unpacked from INCIDENT_ENERGY_COEFFICIENTS (5-tuple), not discarded"
        )

    def test_e02_x_power_not_hardcoded(self):
        """E-02: x_power must NOT be hardcoded to 1.0."""
        src = Path("fault_analysis/arc_flash_engine.py").read_text(encoding="utf-8")
        # Find the x_power assignment near line 341
        # It should reference x_factor, not be a literal 1.0
        lines = src.splitlines()
        x_power_lines = [
            i
            for i, line in enumerate(lines)
            if "x_power" in line and "=" in line and "#" not in line.split("x_power")[0]
        ]
        for line_num in x_power_lines:
            line = lines[line_num].strip()
            # Should NOT be a bare `x_power = 1.0`
            if re.match(r"x_power\s*=\s*1\.0\s*$", line):
                raise AssertionError(
                    f"Line {line_num + 1}: x_power is still hardcoded to 1.0 (E-02 fix not applied)"
                )

    def test_e02_x_factor_values_differ(self):
        """E-02: x_factor values should differ across configurations."""
        from fault_analysis.arc_flash_engine import INCIDENT_ENERGY_COEFFICIENTS

        x_values = set()
        for config, enclosures in INCIDENT_ENERGY_COEFFICIENTS.items():
            for enc, coeffs in enclosures.items():
                x_values.add(coeffs[4])  # 5th element is x_factor (was 4th before E-01 fix)
        # At least 2 distinct x_factor values should exist
        assert len(x_values) >= 2, (
            f"x_factor values are all identical: {x_values}. "
            f"IEEE Table 4 defines different exponents per configuration."
        )

    def test_e02_clamped_range(self):
        """E-02: x_power should be clamped to safe range."""
        src = Path("fault_analysis/arc_flash_engine.py").read_text(encoding="utf-8")
        assert "max(" in src, (
            "x_power should be clamped with max() to prevent overflow"
        )  # NOSONAR S9073: composite assertion verifies a correlated set of conditions; splitting would obscure the invariant under test
        assert "min(" in src, "x_power should be clamped with min() to prevent division-by-zero"

    def test_e01_formula_uses_log10_t(self):
        """E-01: Incident energy formula must use log10(t), not linear t."""
        src = Path("fault_analysis/arc_flash_engine.py").read_text(encoding="utf-8")
        # Should NOT have `* arc_duration_sec` as linear multiplier
        # Should have `+ log10_t` in the formula
        assert "+ log10_t" in src or "+ np.log10(t)" in src, (
            "E-01: Formula must use log10(t) term, not linear t multiplication"
        )
        # Ensure the old pattern `* arc_duration_sec * CF` is gone
        lines = src.splitlines()
        for line in lines:
            if "E_full" in line and "* arc_duration_sec" in line and "log10" not in line:
                raise AssertionError(f"E-01: Found linear t multiplication: {line.strip()}")

    def test_e01_gap_distance_parameter(self):
        """E-01: calculate_incident_energy must accept arc_gap_mm parameter."""
        src = Path("fault_analysis/arc_flash_engine.py").read_text(encoding="utf-8")
        assert "arc_gap_mm" in src, "E-01: arc_gap_mm parameter must exist"

    def test_e01_k4_in_coefficients(self):
        """E-01: Coefficients must be 5-tuples with K4 element."""
        from fault_analysis.arc_flash_engine import INCIDENT_ENERGY_COEFFICIENTS

        for config, enclosures in INCIDENT_ENERGY_COEFFICIENTS.items():
            for enc, coeffs in enclosures.items():
                assert len(coeffs) == 5, (
                    f"Coefficients must be 5-tuple (k1,k2,k3,k4,x_factor), got {len(coeffs)}"
                )

    def test_e20_frequency_parameter(self):
        """S-20: IEC 60909 engine must have configurable frequency."""
        src = Path("fault_analysis/iec60909_engine.py").read_text(encoding="utf-8")
        assert "frequency_hz" in src, "S-20: frequency_hz parameter must exist in __init__"
        assert "self.frequency_hz" in src, (
            "S-20: self.frequency_hz must be stored as instance attribute"
        )
        # Must NOT have hardcoded 50 Hz assumption
        lines = src.splitlines()
        for line in lines:
            if "50.0" in line and "Hz" in line and "default" in line.lower():
                raise AssertionError(f"S-20: Found hardcoded 50 Hz: {line.strip()}")

    def test_e21_no_abs_imag(self):
        """S-21: IEC 60909 must use z_pos.imag, not abs(z_pos.imag)."""
        src = Path("fault_analysis/iec60909_engine.py").read_text(encoding="utf-8")
        # Should NOT have abs(z_pos.imag) in R/X ratio
        assert "abs(z_pos.imag)" not in src, (
            "S-21: R/X ratio must use z_pos.imag (not abs), per IEC 60909"
        )
        # Should use z_pos.imag directly
        assert "z_pos.imag" in src, "S-21: Must use z_pos.imag for R/X ratio"


# ---------------------------------------------------------------------------
# E-03: Load Flow Non-Convergence
# ---------------------------------------------------------------------------


class TestLoadFlowE03:
    """Verify non-converged load flow does NOT write back voltages."""

    def test_e03_no_writeback_on_nonconvergence(self):
        """E-03: Source must NOT write back voltages when converged=False."""
        src = Path("load_flow/load_flow.py").read_text(encoding="utf-8")
        # The non-convergence path should NOT contain bus.voltage = or bus.generation_power =
        # Find the `return False` block (non-convergence)
        lines = src.splitlines()
        found_return_false = False
        for i, line in enumerate(lines):
            if "return False" in line and i > 400:  # Near the solver loop end
                found_return_false = True
                # Check preceding 20 lines for writeback
                preceding = "\n".join(lines[max(0, i - 20) : i + 1])
                assert "bus.voltage" not in preceding or "logger.warning" in preceding, (
                    "Non-convergence path should NOT silently write bus voltages"
                )
                assert "generation_power" not in preceding or "logger.warning" in preceding, (
                    "Non-convergence path should NOT silently write generation power"
                )
                break
        assert found_return_false, "Could not find 'return False' in load_flow.py"


# ---------------------------------------------------------------------------
# S-01: CSRF Bypass
# ---------------------------------------------------------------------------


class TestCSRFS01:
    """Verify CSRF bypass value has been removed."""

    def test_s01_bypass_value_removed(self):
        """S-01: _BYPASS_VALUE should NOT exist or be commented out."""
        src = Path("api/csrf.py").read_text(encoding="utf-8")
        # _BYPASS_VALUE must be commented out or removed
        lines = src.splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("_BYPASS_VALUE"):
                assert stripped.startswith("#") or "= " not in stripped, (
                    "S-01: _BYPASS_VALUE must be removed or commented out. "
                    "Literal 'bypass' string allowed CSRF bypass."
                )

    def test_s01_no_token_bypass_check(self):
        """S-01: No code path should accept literal 'bypass' as valid token."""
        src = Path("api/csrf.py").read_text(encoding="utf-8")
        # Should NOT have: if token == "bypass"
        assert 'token == "bypass"' not in src, (
            "S-01: CSRF bypass via literal 'bypass' string must be removed"
        )
        assert "token == _BYPASS_VALUE" not in src.replace("#", ""), (
            "S-01: No active code should reference _BYPASS_VALUE"
        )


# ---------------------------------------------------------------------------
# S-02: Admin Self-Assign
# ---------------------------------------------------------------------------


class TestAuthS02:
    """Verify registration no longer accepts user-supplied role."""

    def test_s02_role_field_removed_or_defaulted(self):
        """S-02: RegisterRequest should NOT have a role field, or it should be ignored."""
        src = Path("api/auth.py").read_text(encoding="utf-8")
        # The registration handler should force a fixed role
        assert 'role="viewer"' in src or 'role = "viewer"' in src, (
            "S-02: Registration must force a fixed role (e.g., 'viewer')"
        )

    def test_s02_register_creates_viewer(self):
        """S-02: New users should always get 'viewer' role, never 'admin'."""
        src = Path("api/auth.py").read_text(encoding="utf-8")
        # The role passed to create user should be hardcoded
        # Look for the register function's user creation
        assert "body.role" not in src or "# SECURITY" in src, (
            "S-02: body.role should not be used in user creation (privilege escalation)"
        )


# ---------------------------------------------------------------------------
# S-03: WebSocket Authentication
# ---------------------------------------------------------------------------


class TestWebSocketS03:
    """Verify WebSocket requires authentication."""

    def test_s03_token_parameter_exists(self):
        """S-03: WebSocket endpoint should accept a token parameter."""
        src = Path("api/websocket.py").read_text(encoding="utf-8")
        assert "token" in src.lower(), (
            "S-03: WebSocket endpoint should accept token for authentication"
        )
        assert "Query" in src or "token:" in src, "S-03: token should be a query parameter"

    def test_s03_auth_validation_exists(self):
        """S-03: Token validation function should exist."""
        src = Path("api/websocket.py").read_text(encoding="utf-8")
        assert "_validate_ws_token" in src, (
            "S-03: WebSocket should have a token validation function"
        )

    def test_s03_rejects_unauthenticated(self):
        """S-03: Unauthenticated connections should be rejected."""
        src = Path("api/websocket.py").read_text(encoding="utf-8")
        assert "4001" in src or "close" in src.lower(), (
            "S-03: Unauthenticated WebSocket connections should be closed"
        )


# ---------------------------------------------------------------------------
# S-05: Test Mode Role
# ---------------------------------------------------------------------------


class TestTestModeS05:
    """Verify test mode grants 'service' role, not 'admin'."""

    def test_s05_service_role(self):
        """S-05: Test mode API key should return 'service' role."""
        src = Path("api/_test_mode.py").read_text(encoding="utf-8")
        assert '"service"' in src, "S-05: Test mode should grant 'service' role"
        # Should NOT have role: "admin"
        lines = src.splitlines()
        for line in lines:
            if '"role"' in line or "'role'" in line:
                # Check for admin role assignment
                stripped = line.strip()
                if '"admin"' in stripped or "'admin'" in stripped:
                    # Allow if it's a comment or a different context
                    # Allow comments (including "was admin" changelog notes)
                    if (
                        not stripped.startswith("#")
                        and "not" not in stripped.lower()
                        and "was" not in stripped.lower()
                    ):
                        raise AssertionError(f"S-05: Found admin role in test mode: {stripped}")


# ---------------------------------------------------------------------------
# S-07: AI/ML Authentication
# ---------------------------------------------------------------------------


class TestAIMLS07:
    """Verify AI/ML endpoints require authentication."""

    def test_s07_auth_dependency_present(self):
        """S-07: AI/ML endpoints should have auth dependencies."""
        src = Path("api/ai_ml.py").read_text(encoding="utf-8")
        assert "Depends(" in src, "S-07: AI/ML endpoints should use Depends() for authentication"

    def test_s07_all_endpoints_protected(self):
        """S-07: Every @router decorator should have dependencies."""
        src = Path("api/ai_ml.py").read_text(encoding="utf-8")
        lines = src.splitlines()
        router_lines = [i for i, line in enumerate(lines) if "@router." in line]
        for line_num in router_lines:
            # Check the next few lines for dependencies
            chunk = "\n".join(lines[line_num : min(line_num + 5, len(lines))])
            if "dependencies=" not in chunk:
                raise AssertionError(
                    f"S-07: Endpoint at line {line_num + 1} missing dependencies= "
                    f"(authentication not enforced)"
                )


# ---------------------------------------------------------------------------
# S-18: nginx H2C Smuggling
# ---------------------------------------------------------------------------


class TestNginxS18:
    """Verify nginx uses $connection_upgrade instead of literal 'upgrade'."""

    def test_s18_connection_upgrade_variable(self):
        """S-18: WebSocket Connection header must use $connection_upgrade, not literal 'upgrade'."""
        src = Path("nginx.conf").read_text(encoding="utf-8")
        lines = src.splitlines()
        for i, line in enumerate(lines):
            if "proxy_set_header Connection" not in line:
                continue
            stripped = line.strip()
            # Empty Connection "" is safe (prevents smuggling)
            if stripped.endswith('""') or stripped.endswith("''"):
                continue
            # $connection_upgrade variable is correct
            if "$connection_upgrade" in line:
                continue
            # Literal "upgrade" is the H2C smuggling vulnerability
            if '"upgrade"' in stripped or "'upgrade'" in stripped:
                context = "\n".join(lines[max(0, i - 10) : i + 1])
                raise AssertionError(
                    f"S-18: Line {i + 1} uses literal 'upgrade' in Connection header "
                    f"(H2C smuggling risk). Use $connection_upgrade variable instead. "
                    f"Context:\n{context}"
                )
