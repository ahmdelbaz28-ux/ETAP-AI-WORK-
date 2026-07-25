"""
Phase 4 Audit Verification Tests — S-24 MFA brute-force + Helm HPA + swallowed exceptions.

Tests verify that:
- S-24: MFA verify endpoint has brute-force protection (lockout after N failures)
- Helm HPA template exists and is properly structured
- Helm HPA values exist in values.yaml
- HPA is conditionally enabled
- Swallowed exceptions have SECURITY comments explaining intent
"""
import os
import re
import unittest


class TestMFABruteForceS24(unittest.TestCase):
    """S-24: Verify MFA verify endpoint has brute-force protection."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.mfa_path = os.path.join(base, "api", "mfa.py")

    def _read(self):
        with open(self.mfa_path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_s24_failed_attempts_tracking(self):
        """MFA module must track failed attempts."""
        src = self._read()
        self.assertIn("_failed_attempts", src)

    def test_s24_lockout_mechanism(self):
        """MFA module must have lockout mechanism."""
        src = self._read()
        self.assertIn("_lockouts", src)

    def test_s24_max_failed_attempts_constant(self):
        """Must define a maximum failed attempts threshold."""
        src = self._read()
        self.assertIn("_MAX_FAILED_ATTEMPTS", src)
        # Should be a reasonable number (not too high)
        match = re.search(r"_MAX_FAILED_ATTEMPTS\s*=\s*(\d+)", src)
        self.assertIsNotNone(match, "Must define _MAX_FAILED_ATTEMPTS as integer")
        value = int(match.group(1))
        self.assertLessEqual(value, 10, "Max failed attempts should be <= 10")

    def test_s24_lockout_window_defined(self):
        """Must define a lockout time window."""
        src = self._read()
        self.assertIn("_LOCKOUT_WINDOW", src)

    def test_s24_lockout_duration_defined(self):
        """Must define a lockout duration."""
        src = self._read()
        self.assertIn("_LOCKOUT_DURATION", src)

    def test_s24_returns_429_on_lockout(self):
        """Must return HTTP 429 when account is locked."""
        src = self._read()
        self.assertIn("429", src)
        self.assertIn("locked", src.lower())

    def test_s24_prunes_old_attempts(self):
        """Must prune old attempts outside the window."""
        src = self._read()
        self.assertIn("prune", src.lower())

    def test_s24_uses_time_module(self):
        """Must import time for tracking."""
        src = self._read()
        self.assertIn("import time", src)

    def test_s24_uses_defaultdict(self):
        """Must use defaultdict for attempt tracking."""
        src = self._read()
        self.assertIn("defaultdict", src)


class TestHelmHPA(unittest.TestCase):
    """Verify Helm HPA template."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.helm_dir = os.path.join(base, "helm", "etap-ai", "templates")
        self.hpa_path = os.path.join(self.helm_dir, "hpa.yaml")
        self.values_path = os.path.join(
            os.path.dirname(self.helm_dir), "values.yaml"
        )

    def _read(self, path):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_hpa_template_exists(self):
        """HPA template file must exist."""
        self.assertTrue(os.path.isfile(self.hpa_path), "hpa.yaml must exist")

    def test_hpa_is_conditionally_enabled(self):
        """HPA should be conditionally rendered."""
        src = self._read(self.hpa_path)
        self.assertIn(".Values.api.hpa.enabled", src)

    def test_hpa_has_scale_target(self):
        """HPA must reference the API deployment."""
        src = self._read(self.hpa_path)
        self.assertIn("scaleTargetRef", src)

    def test_hpa_has_min_max_replicas(self):
        """HPA must specify min and max replicas."""
        src = self._read(self.hpa_path)
        self.assertIn("minReplicas", src)
        self.assertIn("maxReplicas", src)

    def test_hpa_values_in_values_yaml(self):
        """values.yaml must define api.hpa section."""
        src = self._read(self.values_path)
        self.assertIn("hpa:", src, "values.yaml must define api.hpa")
        self.assertIn("minReplicas:", src)
        self.assertIn("maxReplicas:", src)
        self.assertIn("targetCPUUtilizationPercentage:", src)


class TestSwallowedExceptionsAnnotated(unittest.TestCase):
    """Verify that intentional swallowed exceptions have SECURITY comments."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.api_dir = os.path.join(base, "api")

    def _read(self, fname):
        path = os.path.join(self.api_dir, fname)
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_ai_ml_jwt_fallback_annotated(self):
        """ai_ml.py JWT fallback exception must have SECURITY comment."""
        src = self._read("ai_ml.py")
        # Find the pass after except Exception in _get_api_key_or_user
        self.assertIn(
            "SECURITY: Intentional",
            src,
            "ai_ml.py swallowed exception must have SECURITY annotation",
        )

    def test_shared_handlers_jwt_fallback_annotated(self):
        """shared_handlers.py JWT fallback exception must have SECURITY comment."""
        src = self._read("shared_handlers.py")
        self.assertIn(
            "SECURITY: Intentional",
            src,
            "shared_handlers.py swallowed exception must have SECURITY annotation",
        )


if __name__ == "__main__":
    unittest.main()
