"""
Phase 5 Audit Verification Tests — Gap fixes found during self-critique.

Tests verify that:
- S-09 gap fix: get_current_user() now checks JWT blacklist (not just get_api_key)
- S-10 gap fix: delete_many() and presign() now call _validate_key()
- S-10 gap fix: list_objects() validates prefix
- S-23 gap fix: settings.py no longer leaks str(exc) in JSONResponse
- S-23 gap fix: agents.py no longer leaks str(exc) in JSONResponse
- S-23 gap fix: magic_links.py no longer leaks str(exc) in JSONResponse
- S-23 gap fix: email_digest.py no longer leaks str(exc) in JSONResponse
- S-23 gap fix: shared_handlers.py no longer leaks {exc} in f-strings
- S-23 gap fix: routes.py health endpoint no longer leaks str(numpy_err)
- S-23 gap fix: ValueError detail=str(ve) replaced in settings/validation/studies
- S-07 gap fix: ai_ml.py uses hmac.compare_digest for API-key comparison
- S-07 gap fix: ai_ml.py checks token type (access only)
- S-06 docs fix: csrf.py no longer references removed bypass
- S-24 lock fix: mfa.py uses threading.Lock for shared state
"""
import os
import re
import unittest


class TestS09BlacklistGetCurrentUser(unittest.TestCase):
    """S-09 gap fix: get_current_user() must check JWT blacklist."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.dep_path = os.path.join(base, "api", "dependencies.py")

    def _read(self):
        with open(self.dep_path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_get_current_user_has_blacklist_check(self):
        """get_current_user must check token blacklist after type check."""
        src = self._read()
        # Find get_current_user function
        gcu_match = re.search(
            r"async def get_current_user\(.+?\n(?=\n[a-z]|\Z)",
            src, re.DOTALL,
        )
        self.assertIsNotNone(gcu_match, "get_current_user function must exist")
        gcu_body = gcu_match.group(0)
        self.assertIn("_is_token_blacklisted", gcu_body,
                       "get_current_user must check token blacklist")

    def test_get_current_user_blacklist_is_lazy_import(self):
        """Blacklist check in get_current_user must use lazy import."""
        src = self._read()
        self.assertGreaterEqual(src.count("from api.auth import _is_token_blacklisted"), 2)

    def test_get_current_user_blacklist_checks_jti(self):
        """Blacklist check must verify JTI, not just import."""
        src = self._read()
        self.assertIn("if jti:", src)
        self.assertIn("await _is_token_blacklisted(jti)", src)


class TestS10GapFixes(unittest.TestCase):
    """S-10 gap fix: delete_many, presign, list_objects must validate keys."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.r2_path = os.path.join(base, "api", "r2_storage.py")

    def _read(self):
        with open(self.r2_path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_delete_many_validates_keys(self):
        """delete_many must call _validate_key for each key."""
        src = self._read()
        # Find delete_many function
        dm_match = re.search(
            r"async def delete_many\(.+?\n(?=\n[a-z]|\Z)",
            src, re.DOTALL,
        )
        self.assertIsNotNone(dm_match, "delete_many function must exist")
        dm_body = dm_match.group(0)
        self.assertIn("_validate_key", dm_body,
                       "delete_many must call _validate_key")

    def test_presign_validates_key(self):
        """presign must call _validate_key."""
        src = self._read()
        ps_match = re.search(
            r"def presign\(.+?\n(?=\n[a-z]|\Z)",
            src, re.DOTALL,
        )
        self.assertIsNotNone(ps_match, "presign function must exist")
        ps_body = ps_match.group(0)
        self.assertIn("_validate_key", ps_body,
                       "presign must call _validate_key")

    def test_list_objects_validates_prefix(self):
        """list_objects must validate prefix."""
        src = self._read()
        lo_match = re.search(
            r"async def list_objects\(.+?\n(?=\n[a-z]|\Z)",
            src, re.DOTALL,
        )
        self.assertIsNotNone(lo_match, "list_objects function must exist")
        lo_body = lo_match.group(0)
        self.assertIn("_validate_key", lo_body,
                       "list_objects must call _validate_key on prefix")


class TestS23GapFixes(unittest.TestCase):
    """S-23 gap fix: Additional files that leaked str(exc)."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.api_dir = os.path.join(base, "api")

    def _read(self, fname):
        path = os.path.join(self.api_dir, fname)
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_settings_no_str_exc_in_json_response(self):
        """settings.py must not leak str(exc) in JSONResponse."""
        src = self._read("settings.py")
        # Find all JSONResponse blocks and verify no str(exc) in content
        jr_matches = re.finditer(r'JSONResponse\([^)]*content=\{[^}]+\}', src, re.DOTALL)
        for m in jr_matches:
            self.assertNotIn("str(exc)", m.group(0),
                              f"settings.py JSONResponse leaks str(exc): {m.group(0)[:100]}")

    def test_agents_no_str_exc_in_json_response(self):
        """agents.py must not leak str(exc) in JSONResponse."""
        src = self._read("agents.py")
        jr_matches = re.finditer(r'JSONResponse\([^)]*content=\{[^}]+\}', src, re.DOTALL)
        for m in jr_matches:
            self.assertNotIn("str(exc)", m.group(0),
                              f"agents.py JSONResponse leaks str(exc): {m.group(0)[:100]}")

    def test_magic_links_no_str_exc(self):
        """magic_links.py must not leak str(exc) in JSONResponse."""
        src = self._read("magic_links.py")
        self.assertNotIn('"message": str(exc)', src)
        self.assertNotIn('"message": str(e)', src)

    def test_email_digest_no_str_exc(self):
        """email_digest.py must not leak str(exc) in JSONResponse."""
        src = self._read("email_digest.py")
        self.assertNotIn('"error": str(exc)', src)
        self.assertNotIn('"error": str(e)', src)

    def test_shared_handlers_no_exc_fstring(self):
        """shared_handlers.py must not leak {exc} in error response dicts."""
        src = self._read("shared_handlers.py")
        # Check for f-strings with {exc} in return dicts
        self.assertNotIn('"error": f"ETAP Expert agent error: {exc}', src)
        self.assertNotIn('"error": f"ETAP GUI agent error: {exc}', src)
        self.assertNotIn('Details: {exc}', src)

    def test_routes_numpy_error_generic(self):
        """routes.py health endpoint must not leak str(numpy_err)."""
        src = self._read("routes.py")
        self.assertNotIn('str(numpy_err)', src,
                          "routes.py must not leak str(numpy_err) in health response")

    def test_validation_no_detail_str_ve(self):
        """validation.py must not use detail=str(ve)."""
        src = self._read("validation.py")
        self.assertNotIn('detail=str(ve)', src)

    def test_studies_no_detail_str_ve(self):
        """studies.py must not use detail=str(ve)."""
        src = self._read("studies.py")
        self.assertNotIn('detail=str(ve)', src)

    def test_settings_no_detail_str_exc(self):
        """settings.py must not use detail=str(exc) for ValueError."""
        src = self._read("settings.py")
        # Should NOT have detail=str(exc) (ValueError handler)
        ve_matches = re.finditer(r'except ValueError', src)
        for m in ve_matches:
            # Get surrounding context
            start = m.start()
            end = min(start + 200, len(src))
            context = src[start:end]
            self.assertNotIn("detail=str(", context,
                              "ValueError handler must not use detail=str()")


class TestS07GapFixes(unittest.TestCase):
    """S-07 gap fix: ai_ml.py API-key timing + JWT validation."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.path = os.path.join(base, "api", "ai_ml.py")

    def _read(self):
        with open(self.path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_uses_hmac_compare_digest(self):
        """ai_ml.py must use hmac.compare_digest for API key comparison."""
        src = self._read()
        self.assertIn("hmac.compare_digest", src,
                       "ai_ml.py must use hmac.compare_digest for constant-time comparison")
        self.assertIn("import hmac", src)

    def test_jwt_rejects_non_access_tokens(self):
        """ai_ml.py JWT path must reject non-access tokens."""
        src = self._read()
        # Find _get_api_key_or_user function
        func_match = re.search(
            r"async def _get_api_key_or_user\(.+?(?=async def|\Z)",
            src, re.DOTALL,
        )
        self.assertIsNotNone(func_match)
        func_body = func_match.group(0)
        self.assertIn('payload.get("type") != "access"', func_body,
                       "ai_ml.py JWT path must check token type")


class TestS06DocsFix(unittest.TestCase):
    """S-06 docs fix: csrf.py must not reference removed bypass."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.path = os.path.join(base, "api", "csrf.py")

    def _read(self):
        with open(self.path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_no_bypass_in_module_docstring(self):
        """Module docstring must not reference bypass."""
        src = self._read()
        # Module docstring is at top
        doc_end = src.index('"""', src.index('"""') + 3) + 3
        module_doc = src[:doc_end]
        self.assertNotIn("bypass", module_doc.lower(),
                          "Module docstring must not reference removed bypass")

    def test_no_bypass_in_class_docstring(self):
        """CSRFMiddleware class docstring must not reference bypass."""
        src = self._read()
        class_match = re.search(r'class CSRFMiddleware\(.+?"""', src, re.DOTALL)
        self.assertIsNotNone(class_match)
        class_doc = class_match.group(0)
        self.assertNotIn("bypass", class_doc.lower(),
                          "Class docstring must not reference removed bypass")

    def test_no_bypass_in_error_message(self):
        """Error response must not tell clients to use bypass."""
        src = self._read()
        self.assertNotIn("use X-CSRF-Token: bypass", src)


class TestS24LockFix(unittest.TestCase):
    """S-24 lock fix: mfa.py must use threading.Lock."""

    def setUp(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.path = os.path.join(base, "api", "mfa.py")

    def _read(self):
        with open(self.path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def test_imports_threading(self):
        """mfa.py must import threading."""
        src = self._read()
        self.assertIn("import threading", src)

    def test_has_mfa_lock(self):
        """mfa.py must define a threading.Lock instance."""
        src = self._read()
        self.assertIn("_mfa_lock", src)
        self.assertIn("threading.Lock()", src)

    def test_lock_used_in_verify(self):
        """verify_totp must use the lock for shared state access."""
        src = self._read()
        func_match = re.search(
            r"async def verify_totp\(.+?(?=@router|\Z)",
            src, re.DOTALL,
        )
        self.assertIsNotNone(func_match)
        func_body = func_match.group(0)
        self.assertIn("with _mfa_lock:", func_body,
                       "verify_totp must use threading.Lock")


if __name__ == "__main__":
    unittest.main()
