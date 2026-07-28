"""
Phase 3 Audit Verification Tests — S-23 Error Info Leak + Helm PDB/Secret.

Tests verify that:
- S-23: Internal error details (str(e)) are NOT exposed in API responses
- S-23: Error details ARE still logged server-side
- Helm PDB template exists and is properly structured
- Helm secret.yaml supports external secret annotations
- Helm secret.yaml does not hardcode secret values
"""

import ast
import os
import re
import textwrap
import unittest


class TestErrorInfoLeakS23(unittest.TestCase):
    """S-23: Verify internal error details are not leaked in API responses."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.ai_ml_path = os.path.join(base, "api", "ai_ml.py")
        self.equipment_path = os.path.join(base, "api", "equipment.py")
        self.email_dash_path = os.path.join(base, "api", "email_dashboard.py")

    def _read(self, path):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()

    # --- api/ai_ml.py ---
    def test_s23_ai_ml_no_str_e_in_json_response(self):
        """JSONResponse errors must NOT contain str(e)."""
        src = self._read(self.ai_ml_path)
        # Find all JSONResponse content blocks that contain "errors"
        # They should use "Internal server error" not str(e)
        json_response_lines = [
            line for line in src.splitlines() if "JSONResponse" in line and "errors" in line
        ]
        for line in json_response_lines:
            self.assertNotIn(
                "str(e)",
                line,
                "JSONResponse in ai_ml.py leaks internal error via str(e)",
            )

    def test_s23_ai_ml_uses_generic_error_message(self):
        """Error responses use generic 'Internal server error' message (via MSG_INTERNAL_ERROR constant)."""
        src = self._read(self.ai_ml_path)
        # Accept either the literal string or the imported constant
        self.assertTrue(
            '"Internal server error"' in src or "MSG_INTERNAL_ERROR" in src,
            "ai_ml.py should use generic error message in responses (literal string or MSG_INTERNAL_ERROR constant)",
        )

    def test_s23_ai_ml_still_logs_errors(self):
        """Server-side logging must still contain error details."""
        src = self._read(self.ai_ml_path)
        # At least one logger.exception should remain with str(e)
        self.assertGreaterEqual(
            src.count("logger.exception"),
            5,
            "ai_ml.py should log errors server-side with full details",
        )

    # --- api/equipment.py ---
    def test_s23_equipment_no_str_e_in_error_append(self):
        """Import error messages should NOT leak str(e) to clients."""
        src = self._read(self.equipment_path)
        # Find "errors.append" lines — they should not contain str(e)
        error_append_lines = [line for line in src.splitlines() if "errors.append" in line]
        for line in error_append_lines:
            self.assertNotIn(
                "str(e)",
                line,
                "equipment.py errors.append leaks internal error via str(e)",
            )

    def test_s23_equipment_generic_json_decode_error(self):
        """JSONDecodeError response should use generic message."""
        src = self._read(self.equipment_path)
        # The detail for JSONDecodeError should be generic
        self.assertIn(
            "could not parse",
            src,
            "equipment.py JSON decode error should use generic message",
        )

    def test_s23_equipment_logs_import_errors(self):
        """Import errors should still be logged server-side."""
        src = self._read(self.equipment_path)
        self.assertIn(
            "logger.warning",
            src,
            "equipment.py should log import errors server-side",
        )

    # --- api/email_dashboard.py ---
    def test_s23_email_dashboard_no_jwt_error_detail(self):
        """JWT error response must NOT leak jwt_err details."""
        src = self._read(self.email_dash_path)
        # The detail should NOT contain the jwt_err variable
        self.assertNotIn(
            'detail=f"Invalid JWT token: {jwt_err}',
            src,
            "email_dashboard.py leaks JWT error details in response",
        )

    def test_s23_email_dashboard_generic_jwt_error(self):
        """JWT error should use generic auth failure message."""
        src = self._read(self.email_dash_path)
        self.assertIn(
            "Invalid or expired authentication token",
            src,
            "email_dashboard.py should use generic auth error message",
        )


class TestHelmPBDSecret(unittest.TestCase):
    """Verify Helm PDB and secret template improvements."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.helm_dir = os.path.join(base, "helm", "etap-ai", "templates")
        self.pdb_path = os.path.join(self.helm_dir, "pdb.yaml")
        self.secret_path = os.path.join(self.helm_dir, "secret.yaml")

    def _read(self, path):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_pdb_template_exists(self):
        """PDB template file must exist."""
        self.assertTrue(
            os.path.isfile(self.pdb_path),
            "pdb.yaml must exist in helm templates",
        )

    def test_pdb_has_pod_disruption_budget_kind(self):
        """PDB template must define PodDisruptionBudget resource."""
        src = self._read(self.pdb_path)
        self.assertIn("PodDisruptionBudget", src)

    def test_pdb_has_min_available(self):
        """PDB must specify minAvailable."""
        src = self._read(self.pdb_path)
        self.assertIn("minAvailable", src)

    def test_pdb_has_selector(self):
        """PDB must have a selector matching the api pods."""
        src = self._read(self.pdb_path)
        self.assertIn("selector", src)

    def test_pdb_is_conditionally_enabled(self):
        """PDB should be conditionally rendered (enabled flag)."""
        src = self._read(self.pdb_path)
        self.assertIn(".Values.api.pdb.enabled", src)

    def test_pdb_values_exist_in_values_yaml(self):
        """values.yaml must define api.pdb.enabled and api.pdb.minAvailable."""
        values_path = os.path.join(self.helm_dir, "..", "values.yaml")
        values_path = os.path.normpath(values_path)
        src = self._read(values_path)
        self.assertIn("pdb:", src, "values.yaml must define api.pdb section")
        self.assertIn("enabled:", src, "values.yaml must define api.pdb.enabled")
        self.assertIn("minAvailable:", src, "values.yaml must define api.pdb.minAvailable")

    def test_secret_no_hardcoded_values(self):
        """Secret template must NOT hardcode any secret values."""
        src = self._read(self.secret_path)
        # Must use Helm template functions (b64enc) not hardcoded base64
        hardcoded_b64 = re.findall(
            r'data:\s*\n\s+\w+-?\w*:\s*["\']?[A-Za-z0-9+/=]{16,}["\']?',
            src,
        )
        self.assertEqual(
            len(hardcoded_b64),
            0,
            "secret.yaml must not contain hardcoded base64 values",
        )

    def test_secret_supports_external_annotations(self):
        """Secret template should support external secret annotations."""
        src = self._read(self.secret_path)
        self.assertIn(
            "externalSecretAnnotations",
            src,
            "secret.yaml should support external secret annotations for vault/sealed-secrets",
        )

    def test_secret_does_not_contain_api_key(self):
        """Helm-managed secret must NOT contain a conditional api-key block.

        SECURITY REFACTOR (2026-07-28, commit 2917e42b): The API key was moved
        OUT of the Helm-managed secret template and into a pre-created K8s Secret
        (`k8s/etap-api-key-secret.yaml`). The Helm `deployment.yaml` references
        this pre-created Secret via `secretKeyRef`. This pattern is more secure
        because:

        1. The API key is NEVER baked into Helm values (which are typically
           committed to git, even though they shouldn't be).
        2. The pre-created Secret can be provisioned out-of-band via sealed-secrets,
           external-secrets-operator, or Vault — without re-deploying the chart.
        3. Helm upgrades do not risk overwriting the API key.

        This test enforces the new design. The OLD test
        (`test_secret_conditional_api_key`) checked for the now-removed pattern
        `{{- if .Values.env.ENGINEERING_SERVICE_API_KEY }}` and was failing
        because the conditional was correctly removed.

        NOTE: The string "ENGINEERING_SERVICE_API_KEY" MAY appear in the file's
        explanatory header comment (documenting that the key was moved OUT).
        That is correct and expected — what matters is that no Helm template
        directive references it (i.e., no `{{- if .Values.env.ENGINEERING_SERVICE_API_KEY }}`
        and no `{{ .Values.env.ENGINEERING_SERVICE_API_KEY | b64enc }}`).
        """
        src = self._read(self.secret_path)
        # The conditional block (the security-relevant pattern) must be GONE.
        self.assertNotIn(
            "{{- if .Values.env.ENGINEERING_SERVICE_API_KEY }}",
            src,
            "Helm-managed secret.yaml must NOT contain "
            "'{{- if .Values.env.ENGINEERING_SERVICE_API_KEY }}' conditional block "
            "(API key was moved to pre-created etap-api-key Secret)",
        )
        # The b64enc of the API key must also be GONE.
        self.assertNotIn(
            ".Values.env.ENGINEERING_SERVICE_API_KEY | b64enc",
            src,
            "Helm-managed secret.yaml must NOT b64enc the API key "
            "(API key was moved to pre-created etap-api-key Secret)",
        )

    def test_deployment_references_precreated_api_key_secret(self):
        """Deployment template must reference the pre-created etap-api-key Secret.

        Verifies the second half of the security refactor: the deployment
        template must wire the `ENGINEERING_SERVICE_API_KEY` env var from the
        pre-created `etap-api-key` Secret via `secretKeyRef`.
        """
        deployment_path = os.path.join(self.helm_dir, "deployment.yaml")
        src = self._read(deployment_path)
        self.assertIn(
            "name: etap-api-key",
            src,
            "deployment.yaml must reference the pre-created 'etap-api-key' Secret",
        )
        self.assertIn(
            "secretKeyRef",
            src,
            "deployment.yaml must use secretKeyRef to wire ENGINEERING_SERVICE_API_KEY",
        )

    def test_precreated_api_key_secret_manifest_exists(self):
        """The pre-created etap-api-key Secret manifest must exist.

        Verifies the third part of the security refactor: the manifest that
        operators apply BEFORE Helm deployment (documented in
        `k8s/etap-api-key-secret.yaml`) must exist.
        """
        # self.helm_dir = <repo>/helm/etap-ai/templates — go up 3 levels to repo root.
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(self.helm_dir)))
        manifest_path = os.path.join(repo_root, "k8s", "etap-api-key-secret.yaml")
        self.assertTrue(
            os.path.isfile(manifest_path),
            f"k8s/etap-api-key-secret.yaml must exist (pre-created Secret manifest) "
            f"— looked at: {manifest_path}",
        )
        src = self._read(manifest_path)
        self.assertIn("name: etap-api-key", src, "Manifest must define the etap-api-key Secret")
        self.assertIn(
            "api-key:",
            src,
            "Manifest must define the api-key data key inside the Secret",
        )


class TestS23AllAPIModulesComprehensive(unittest.TestCase):
    """Comprehensive check: NO api/*.py file leaks str(e) in client responses."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.api_dir = os.path.join(base, "api")
        # Files known to have exception handlers
        self.api_files = [
            f
            for f in os.listdir(self.api_dir)
            if f.endswith(".py")
            and not f.startswith("_")
            and f != "__init__.py"
            and f != "security_audit.py"
        ]

    def _read(self, path):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_s23_no_str_e_in_any_json_response(self):
        """No API file should leak str(e) inside JSONResponse content."""
        for fname in self.api_files:
            path = os.path.join(self.api_dir, fname)
            src = self._read(path)
            for lineno, line in enumerate(src.splitlines(), 1):
                if "JSONResponse" in line and "errors" in line and "str(e)" in line:
                    self.fail(f"{fname}:{lineno} leaks str(e) in JSONResponse: {line.strip()}")

    def test_s23_no_str_e_in_http_exception_detail(self):
        """No API file should leak str(e) in HTTPException detail."""
        for fname in self.api_files:
            path = os.path.join(self.api_dir, fname)
            src = self._read(path)
            for lineno, line in enumerate(src.splitlines(), 1):
                if "HTTPException" in line and "detail=" in line and "str(e)" in line:
                    self.fail(f"{fname}:{lineno} leaks str(e) in HTTPException: {line.strip()}")

    def test_s23_no_str_e_in_errors_append(self):
        """No API file should leak str(e) in errors.append (import handlers)."""
        for fname in self.api_files:
            path = os.path.join(self.api_dir, fname)
            src = self._read(path)
            for lineno, line in enumerate(src.splitlines(), 1):
                if "errors.append" in line and "str(e)" in line:
                    self.fail(f"{fname}:{lineno} leaks str(e) in errors.append: {line.strip()}")

    def test_s23_errors_use_generic_message(self):
        """API files that had str(e) should now use generic error messages."""
        problem_files = [
            "ai_ml.py",
            "agents.py",
            "scada.py",
            "digital_twin.py",
            "mfa.py",
            "shared_handlers.py",
        ]
        for fname in problem_files:
            path = os.path.join(self.api_dir, fname)
            if not os.path.isfile(path):
                continue
            src = self._read(path)
            self.assertTrue(
                "Internal server error" in src or "MSG_INTERNAL_ERROR" in src,
                f"{fname} should contain generic 'Internal server error' message (literal string or MSG_INTERNAL_ERROR constant)",
            )


class TestACPRuntimeLockfileCVE(unittest.TestCase):
    """Verify acp_runtime/pylock.toml also received CVE bumps."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.lock_path = os.path.join(base, "acp_runtime", "pylock.toml")

    def _read(self):
        with open(self.lock_path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_acp_websockets_bumped(self):
        """websockets should be bumped from 12.0 to 13.1."""
        src = self._read()
        self.assertIn('websockets = "13.1"', src, "acp_runtime pylock.toml websockets not bumped")
        self.assertNotIn(
            'websockets = "12.0"', src, "acp_runtime pylock.toml still has old websockets"
        )
