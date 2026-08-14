"""
Notion integration client for AhmedETAP.

Supports TWO authentication modes:

1. **Internal Integration** (default, simpler):
   - Create at: https://www.notion.so/profile/integrations
   - Token format: `ntn_xxx` (new) or `secret_xxx` (legacy)
   - Stored in env: NOTION_API_KEY
   - Shares database/page with integration by ID

2. **Public OAuth Integration** (for multi-tenant apps):
   - Create at: https://www.notion.so/my-integrations (NEW integration → Public)
   - Use OAUTH_CLIENT_ID + OAUTH_CLIENT_SECRET
   - Performs OAuth 2.0 PKCE flow → returns access token per-user
   - Stored in env: OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET

Used by:
  - sync scripts (one-time backfill)
  - daily snapshot jobs (cron)
  - admin dashboard "recent Notion pages" widget

The Notion API version pinned here is 2022-06-28 (stable as of 2025).
"""
from __future__ import annotations

import os
import json
import base64
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass
from typing import Any

NOTION_VERSION = "2022-06-28"
NOTION_BASE = "https://api.notion.com/v1"


@dataclass
class NotionConfig:
    """Resolved Notion configuration loaded from environment."""
    api_key: str | None = None           # internal integration token (ntn_xxx or secret_xxx)
    database_id: str | None = None       # target database for sync
    parent_page_id: str | None = None    # optional parent for new pages
    enabled: bool = False
    # OAuth (public integration) — used when api_key is empty
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    oauth_redirect_uri: str | None = None

    @classmethod
    def from_env(cls) -> "NotionConfig":
        return cls(
            api_key=os.getenv("NOTION_API_KEY") or None,
            database_id=os.getenv("NOTION_DATABASE_ID") or None,
            parent_page_id=os.getenv("NOTION_PARENT_PAGE_ID") or None,
            enabled=os.getenv("NOTION_ENABLED", "false").lower() in ("1", "true", "yes"),
            oauth_client_id=os.getenv("OAUTH_CLIENT_ID") or None,
            oauth_client_secret=os.getenv("OAUTH_CLIENT_SECRET") or None,
            oauth_redirect_uri=os.getenv("OAUTH_REDIRECT_URI") or None,
        )

    @property
    def auth_mode(self) -> str:
        if self.api_key:
            return "internal"
        if self.oauth_client_id and self.oauth_client_secret:
            return "oauth"
        return "none"


class NotionError(Exception):
    """Raised when Notion API returns an error."""
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(f"Notion API {status} {code}: {message}")


class NotionClient:
    """Thin wrapper around the Notion REST API.

    Uses urllib instead of requests/supabase SDK to avoid adding dependencies
    — the rest of AhmedETAP uses httpx for HTTP. We use stdlib here because
    Notion is an optional integration; if the user doesn't configure it,
    we don't want to slow down app startup by importing httpx eagerly.
    """

    def __init__(self, config: NotionConfig | None = None):
        self.config = config or NotionConfig.from_env()

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _headers(self, access_token: str | None = None) -> dict[str, str]:
        token = access_token or self.config.api_key
        if not token:
            raise NotionError(401, "no_token",
                              "No Notion token configured. Set NOTION_API_KEY or perform OAuth flow.")
        return {
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method: str, path: str, *,
                 body: dict | None = None,
                 params: dict | None = None,
                 access_token: str | None = None) -> dict:
        url = f"{NOTION_BASE}/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(access_token),
                                     method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            try:
                err_body = json.loads(raw)
                code = err_body.get("code", "error")
                msg = err_body.get("message", raw)
            except json.JSONDecodeError:
                code = "http_error"
                msg = raw
            raise NotionError(e.code, code, msg) from None
        except urllib.error.URLError as e:
            raise NotionError(-1, "network", str(e)) from None

    # ------------------------------------------------------------------
    # Bot / user info (validates token)
    # ------------------------------------------------------------------
    def get_me(self) -> dict:
        """GET /v1/users/me — verify token validity + retrieve bot identity."""
        return self._request("GET", "users/me")

    # ------------------------------------------------------------------
    # Database operations
    # ------------------------------------------------------------------
    def get_database(self, database_id: str | None = None) -> dict:
        """GET /v1/databases/{id} — retrieve database schema."""
        db_id = database_id or self.config.database_id
        if not db_id:
            raise NotionError(400, "no_database",
                              "No database_id provided and NOTION_DATABASE_ID is empty.")
        return self._request("GET", f"databases/{db_id}")

    def query_database(self, database_id: str | None = None, *,
                       filter: dict | None = None,
                       sorts: list | None = None,
                       start_cursor: str | None = None,
                       page_size: int = 100) -> dict:
        """POST /v1/databases/{id}/query — list pages matching filter."""
        db_id = database_id or self.config.database_id
        if not db_id:
            raise NotionError(400, "no_database",
                              "No database_id provided and NOTION_DATABASE_ID is empty.")
        body: dict[str, Any] = {"page_size": min(page_size, 100)}
        if filter:
            body["filter"] = filter
        if sorts:
            body["sorts"] = sorts
        if start_cursor:
            body["start_cursor"] = start_cursor
        return self._request("POST", f"databases/{db_id}/query", body=body)

    def create_page(self, parent_id: str | None = None, *,
                    properties: dict,
                    children: list | None = None) -> dict:
        """POST /v1/pages — create a new page in a database or under a parent page."""
        parent_id = parent_id or self.config.parent_page_id or self.config.database_id
        if not parent_id:
            raise NotionError(400, "no_parent",
                              "No parent_id provided and NOTION_PARENT_PAGE_ID/NOTION_DATABASE_ID empty.")
        # If parent_id matches a 32-char UUID with hyphens, it's a page; otherwise database.
        if self.config.database_id and parent_id == self.config.database_id:
            parent = {"database_id": parent_id}
        else:
            parent = {"page_id": parent_id}
        body = {"parent": parent, "properties": properties}
        if children:
            body["children"] = children
        return self._request("POST", "pages", body=body)

    def update_page(self, page_id: str, *, properties: dict | None = None,
                    archived: bool | None = None) -> dict:
        """PATCH /v1/pages/{id} — update page properties or archive it."""
        body: dict[str, Any] = {}
        if properties is not None:
            body["properties"] = properties
        if archived is not None:
            body["archived"] = archived
        return self._request("PATCH", f"pages/{page_id}", body=body)

    # ------------------------------------------------------------------
    # OAuth flow (public integration)
    # ------------------------------------------------------------------
    def get_oauth_authorize_url(self, state: str, *,
                                 scope: str = "admin read write",
                                 code_challenge: str | None = None,
                                 code_challenge_method: str = "S256") -> str:
        """Build the authorization URL for redirecting users to Notion."""
        params = {
            "client_id": self.config.oauth_client_id,
            "response_type": "code",
            "owner": "user",
            "redirect_uri": self.config.oauth_redirect_uri,
            "state": state,
        }
        if scope:
            params["scope"] = scope
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = code_challenge_method
        return f"https://api.notion.com/v1/oauth/authorize?{urllib.parse.urlencode(params)}"

    def exchange_oauth_code(self, code: str) -> dict:
        """POST /v1/oauth/token — exchange authorization code for access token.

        Uses HTTP Basic auth with client_id:client_secret.
        Returns: {"access_token": ..., "bot_id": ..., "workspace_name": ...}
        """
        if not (self.config.oauth_client_id and self.config.oauth_client_secret):
            raise NotionError(400, "no_oauth_config",
                              "OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET must be set.")
        auth_basic = base64.b64encode(
            f"{self.config.oauth_client_id}:{self.config.oauth_client_secret}".encode()
        ).decode()
        body = urllib.parse.urlencode({"grant_type": "authorization_code",
                                        "code": code,
                                        "redirect_uri": self.config.oauth_redirect_uri}).encode()
        req = urllib.request.Request(
            f"{NOTION_BASE}/oauth/token",
            data=body,
            headers={
                "Authorization": f"Basic {auth_basic}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Notion-Version": NOTION_VERSION,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            try:
                err = json.loads(raw)
            except json.JSONDecodeError:
                err = {"error": raw}
            raise NotionError(e.code, err.get("error", "http_error"),
                              err.get("error_description", raw)) from None

    # ------------------------------------------------------------------
    # Convenience: full sync (dump database to flat dict)
    # ------------------------------------------------------------------
    def dump_database(self, database_id: str | None = None, *,
                      max_pages: int = 500) -> list[dict]:
        """Read all pages from a database, paginating until exhausted.

        Returns a list of page dicts (each with id, url, properties).
        Caps at max_pages to prevent runaway reads on huge databases.
        """
        pages: list[dict] = []
        cursor = None
        while len(pages) < max_pages:
            resp = self.query_database(database_id, start_cursor=cursor,
                                       page_size=100)
            pages.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
            if not cursor:
                break
        return pages[:max_pages]


def is_configured() -> bool:
    """Check whether Notion is configured at all (used by app health check)."""
    cfg = NotionConfig.from_env()
    return cfg.enabled and cfg.auth_mode != "none"


def get_client() -> NotionClient | None:
    """Factory used by app code; returns None if Notion is disabled."""
    cfg = NotionConfig.from_env()
    if not cfg.enabled:
        return None
    return NotionClient(cfg)


if __name__ == "__main__":
    # Self-test: validate token + show bot identity
    import sys
    client = get_client()
    if client is None:
        print("Notion is disabled (NOTION_ENABLED != true).")
        sys.exit(0)
    print(f"Auth mode: {client.config.auth_mode}")
    if client.config.auth_mode == "internal":
        try:
            me = client.get_me()
            print(f"✓ Internal token valid — bot name: {me.get('name')}")
            if client.config.database_id:
                db = client.get_database()
                print(f"✓ Database accessible — title: {db.get('title', [{}])[0].get('plain_text', '?')}")
        except NotionError as e:
            print(f"✗ Notion error: {e}")
            sys.exit(1)
    elif client.config.auth_mode == "oauth":
        state = "selftest"
        url = client.get_oauth_authorize_url(state)
        print(f"OAuth authorize URL: {url}")
        print("(Exchange flow requires a real authorization code — skipping.)")
