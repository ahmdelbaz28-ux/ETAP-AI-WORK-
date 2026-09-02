"""Set SONAR_TOKEN as a GitHub Actions repo secret (official libsodium flow)."""
import base64
import json
import urllib.request

from nacl import encoding, public

import os

# Load secrets from environment variables for security. Ensure they are set before running this script.
TOKEN = os.getenv("SONAR_TOKEN")
GH = os.getenv("GITHUB_PAT")
REPO = os.getenv("GITHUB_REPO", "ahmdelbaz28-ux/ETAP-AI-WORK-")

if not TOKEN or not GH:
    raise RuntimeError("SONAR_TOKEN and GITHUB_PAT environment variables must be set to use this script.")
HEADERS = {
    "Authorization": f"token {GH}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def api(path: str, data: dict | None = None) -> tuple[int, bytes]:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/{path}",
        data=json.dumps(data).encode() if data is not None else None,
        headers=HEADERS,
        method="PUT" if data is not None else "GET",
    )
    with urllib.request.urlopen(req) as resp:
        return resp.status, resp.read()


status, body = api("actions/secrets/public-key")
info = json.loads(body)
pk = public.PublicKey(info["key"].encode(), encoding.Base64Encoder())
sealed = public.SealedBox(pk).encrypt(TOKEN.encode())
payload = {
    "encrypted_value": base64.b64encode(sealed).decode(),
    "key_id": info["key_id"],
}
status, _ = api("actions/secrets/SONAR_TOKEN", payload)
print("PUT SONAR_TOKEN ->", status)
