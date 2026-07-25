"""
Phase 6 Audit Verification Tests — Self-critique round 4 fixes.

Tests verify that:
- S-WS-1: websocket.py uses hmac.compare_digest for API-key comparison
- S-WS-2: websocket.py checks JWT blacklist (revoked tokens)
- S-SH-1: shared_handlers.py engine_error uses generic message (not str(exc))
- S-SH-2: shared_handlers.py ImportError messages don't expose module names
- S-IEC-1: iec60909_engine.py t_min defaults to None (derived from frequency)
- S-CURVE-1: curves.py handles I == Ip singularity with epsilon nudge
"""
import os
import re
import unittest


class TestWebSocketSecurity(unittest.TestCase):
    """S-WS-1/S-WS-2: WebSocket auth security."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.ws_path = os.path.join(base, "api", "websocket.py")

    def _read(self):
        with open(self.ws_path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_ws_uses_hmac_compare_digest(self):
        """websocket.py must use hmac.compare_digest for API-key comparison."""
        src = self._read()
        self.assertIn("hmac.compare_digest", src,
                       "websocket.py must use constant-time comparison")
        self.assertIn("import hmac", src)

    def test_ws_no_plain_equality_for_api_key(self):
        """websocket.py must NOT use == for API key comparison."""
        src = self._read()
        # Find the _validate_ws_token function
        func_match = re.search(
            r"def _validate_ws_token\(.+?(?=\n(?:async )?def |\Z)",
            src, re.DOTALL,
        )
        self.assertIsNotNone(func_match)
        func_body = func_match.group(0)
        # Should NOT have token == api_key
        self.assertNotIn("token == api_key", func_body)

    def test_ws_checks_token_blacklist(self):
        """websocket.py must check JWT blacklist after decoding."""
        src = self._read()
        func_match = re.search(
            r"def _validate_ws_token\(.+?(?=\n(?:async )?def |\Z)",
            src, re.DOTALL,
        )
        self.assertIsNotNone(func_match)
        func_body = func_match.group(0)
        self.assertIn("_is_token_blacklisted", func_body)


class TestSharedHandlersEngineError(unittest.TestCase):
    """S-SH-1/S-SH-2: shared_handlers.py no exception detail leaks."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.path = os.path.join(base, "api", "shared_handlers.py")

    def _read(self):
        with open(self.path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_engine_error_not_str_exc(self):
        """Engine error variable must not be assigned str(exc)."""
        src = self._read()
        self.assertNotIn('engine_error = str(exc)', src)

    def test_engine_error_is_generic(self):
        """Engine error must use a generic message."""
        src = self._read()
        self.assertIn("engine_error = \"Load flow computation failed\"", src)

    def test_import_error_no_module_name_in_response(self):
        """ImportError handlers must not expose module names to clients."""
        src = self._read()
        self.assertNotIn("Missing dependency: {missing_module}", src)
        self.assertNotIn("missing_module = str(ie)", src)


class TestIEC60909tMin(unittest.TestCase):
    """S-IEC-1: t_min default derived from frequency."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.path = os.path.join(base, "fault_analysis", "iec60909_engine.py")

    def _read(self):
        with open(self.path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_calculate_mu_t_min_none(self):
        """_calculate_mu must accept t_min=None."""
        src = self._read()
        self.assertIn("t_min: float | None = None", src)

    def test_calculate_mu_derives_from_frequency(self):
        """_calculate_mu must derive t_min from self.frequency_hz when None."""
        src = self._read()
        self.assertIn("if t_min is None:", src)
        self.assertIn("1.0 / self.frequency_hz", src)

    def test_all_fault_methods_t_min_none(self):
        """All 4 fault methods must have t_min=None (not hardcoded 0.02)."""
        src = self._read()
        self.assertNotIn("t_min: float = 0.02", src)
        # Count occurrences of t_min: float | None = None
        count = src.count("t_min: float | None = None")
        self.assertGreaterEqual(count, 4, "All 4 fault methods + _calculate_mu must use None default")


class TestCurvesSingularity(unittest.TestCase):
    """S-CURVE-1: curves.py handles I == Ip singularity."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.path = os.path.join(base, "curves", "curves.py")

    def _read(self):
        with open(self.path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_has_epsilon_constant(self):
        """curves.py must define an epsilon constant for singularity."""
        src = self._read()
        self.assertIn("_IEC_CURVE_EPSILON", src)

    def test_standard_inverse_uses_epsilon(self):
        """standard_inverse must use epsilon nudge."""
        src = self._read()
        self.assertIn("M = I / Ip if I != Ip else _IEC_CURVE_EPSILON", src)

    def test_no_raw_division(self):
        """No curve should use raw I/Ip without epsilon check."""
        src = self._read()
        # All 4 curves should use M variable with epsilon
        m_count = src.count("M = I / Ip if I != Ip else _IEC_CURVE_EPSILON")
        self.assertEqual(m_count, 4, "All 4 curves must use epsilon nudge")

    def test_curve_returns_finite_at_boundary(self):
        """At I == Ip, curves must return finite (not inf) value."""
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from curves.curves import IEC60255Curves

        result = IEC60255Curves.standard_inverse(1.0, 10.0, 10.0)
        self.assertTrue(self._isfinite(result),
                        f"standard_inverse(I==Ip) must be finite, got {result}")

    @staticmethod
    def _isfinite(v):
        import math
        try:
            return math.isfinite(v)
        except (TypeError, ValueError):
            return False


if __name__ == "__main__":
    unittest.main()
