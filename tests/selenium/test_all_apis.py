#!/usr/bin/env python3
"""Test all Postman collection endpoints against the local API server."""
import json
import urllib.request
import urllib.error
from typing import Any

BASE_URL = "http://127.0.0.1:7860"

# Load endpoints
endpoints = json.load(open('/home/z/my-project/scripts/endpoints.json'))

# Substitute {{base_url}} with actual base URL
def resolve_url(raw_url: str) -> str:
    return raw_url.replace("{{base_url}}", BASE_URL)

# Default headers
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def make_request(ep: dict[str, Any]) -> dict[str, Any]:
    """Make a single HTTP request and return the result."""
    url = resolve_url(ep["raw_url"])
    method = ep["method"]
    body = ep["body_raw"] if ep["body_mode"] == "raw" else None
    
    # Collect headers
    headers = dict(DEFAULT_HEADERS)
    for h in ep["headers"]:
        key = h.get("key", "")
        val = h.get("value", "")
        if key and not key.startswith("Postman"):
            headers[key] = val
    
    result = {
        "name": ep["name"],
        "method": method,
        "url": url,
        "body": body[:200] if body else None,
    }
    
    try:
        data = body.encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            resp_body = resp.read().decode("utf-8", errors="replace")
            result["status"] = status
            result["response"] = resp_body[:500]
            result["success"] = 200 <= status < 400
    except urllib.error.HTTPError as e:
        result["status"] = e.code
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = str(e)
        result["response"] = err_body[:500]
        result["success"] = 200 <= e.code < 400
    except Exception as e:
        result["status"] = 0
        result["response"] = f"EXCEPTION: {e!s}"
        result["success"] = False
    
    return result

# Test all endpoints
results = []
for i, ep in enumerate(endpoints, 1):
    print(f"[{i:2d}/{len(endpoints)}] {ep['method']:6s} {ep['raw_url'][:80]}")
    result = make_request(ep)
    status_icon = "✓" if result["success"] else "✗"
    print(f"        {status_icon} {result['status']}  {result['response'][:100]}")
    results.append(result)

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
success_count = sum(1 for r in results if r["success"])
fail_count = len(results) - success_count
print(f"Total: {len(results)}  Success: {success_count}  Failed: {fail_count}")
print()

# Group by status
from collections import Counter
status_counts = Counter(r["status"] for r in results)
print("Status distribution:")
for status, count in sorted(status_counts.items()):
    print(f"  {status}: {count}")

# Show failures
print("\nFailed endpoints:")
for r in results:
    if not r["success"]:
        print(f"  [{r['status']}] {r['method']} {r['url']}")
        print(f"       Response: {r['response'][:200]}")

# Save full results
json.dump(results, open('/home/z/my-project/scripts/api_test_results.json', 'w'), indent=2)
print(f"\nFull results saved to /home/z/my-project/scripts/api_test_results.json")
