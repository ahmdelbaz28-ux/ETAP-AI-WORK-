"""
Vercel Serverless Function — Email Digest Cron Trigger
======================================================
Triggered by Vercel Cron every hour to call the HF Space digest endpoint.

Vercel Cron only supports internal paths, so this function proxies
the request to the HF Space API.
"""

import os
import urllib.request
import urllib.error
import json


def handler(request):
    """Vercel serverless function handler."""
    hf_space_url = os.getenv("HF_SPACE_URL", "https://ahmdelbaz28-ahmedetap-platform.hf.space")
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
        req = urllib.request.Request(endpoint, method="POST", headers=headers, data=b"{}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return {
                "statusCode": resp.status,
                "body": body,
                "headers": {"Content-Type": "application/json"},
            }
    except urllib.error.HTTPError as e:
        return {
            "statusCode": e.code,
            "body": json.dumps({"error": str(e), "body": e.read().decode("utf-8", errors="replace")[:500]}),
            "headers": {"Content-Type": "application/json"},
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
            "headers": {"Content-Type": "application/json"},
        }
