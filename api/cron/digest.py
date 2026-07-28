"""
Vercel Serverless Function — Email Digest Cron Trigger
======================================================
Triggered by Vercel Cron daily at 08:00 UTC to call the HF Space digest endpoint.

Uses Vercel Python runtime with BaseHTTPRequestHandler interface.
"""

import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    """Vercel Python serverless function handler."""

    def do_POST(self):
        """Handle POST request from Vercel Cron."""
        self._process()

    def do_GET(self):
        """Handle GET request (for manual testing)."""
        self._process()

    def _process(self):
        """Call the HF Space digest endpoint."""
        hf_space_url = os.getenv(
            "HF_SPACE_URL",
            "https://ahmdelbaz28-ahmedetap-platform.hf.space",
        )
        api_key = os.getenv("ENGINEERING_SERVICE_API_KEY", "")
        cf_secret = os.getenv("CLOUDFLARE_ORIGIN_SECRET", "")

        endpoint = f"{hf_space_url}/api/v1/email-digest/schedule/run"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Vercel-Cron/1.0",
        }
        if api_key:
            headers["X-API-Key"] = api_key
        if cf_secret:
            headers["X-Origin-Verify"] = cf_secret

        try:
            req = urllib.request.Request(
                endpoint,
                method="POST",
                headers=headers,
                data=b"{}",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                self._send_json(resp.status, body)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")[:500]
            self._send_json(
                e.code,
                json.dumps({"error": str(e), "body": error_body}),
            )
        except Exception as e:
            self._send_json(
                500,
                json.dumps({"error": str(e)}),
            )

    def _send_json(self, status, body):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))
