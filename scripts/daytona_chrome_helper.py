"""
scripts/daytona_chrome_helper.py — Daytona Standalone Chrome CDP Automation Helper.

Implements automated lifecycle and control of standalone Chromium/Chrome
inside Daytona sandboxes via Chrome DevTools Protocol (CDP) on port 9222.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from typing import Any

logger = logging.getLogger("daytona_chrome")


def get_chrome_launch_command(
    port: int = 9222,
    profile_dir: str = "/tmp/daytona-chrome-profile",
    display: str = ":99",
) -> str:
    """Generate the shell command to launch Chromium with CDP in a Daytona sandbox."""
    return (
        f"mkdir -p {profile_dir} && "
        f"DISPLAY={display} nohup chromium "
        f"--no-sandbox "
        f"--disable-dev-shm-usage "
        f"--remote-debugging-address=0.0.0.0 "
        f"--remote-debugging-port={port} "
        f"--user-data-dir={profile_dir} "
        f"about:blank >/tmp/daytona-chrome.log 2>&1 &"
    )


def get_chrome_stop_command(port: int = 9222) -> str:
    """Generate the command to cleanly stop Chromium in a Daytona sandbox."""
    return (
        f'pkill -f "chromium.*remote-debugging-port={port}" || '
        f'pkill -f "chrome.*remote-debugging-port={port}" || true'
    )


def launch_chrome_in_sandbox(sandbox: Any, port: int = 9222) -> bool:
    """Launch Chromium with CDP remote debugging in a Daytona sandbox."""
    cmd = get_chrome_launch_command(port=port)
    try:
        if hasattr(sandbox, "exec"):
            res = sandbox.exec(f"bash -lc '{cmd}'")
            logger.info("Launched Chrome in sandbox: %s", res)
            return True
        logger.warning("Sandbox object lacks .exec() method")
        return False
    except Exception as exc:
        logger.error("Failed to launch Chrome in Daytona sandbox: %s", exc)
        return False


def stop_chrome_in_sandbox(sandbox: Any, port: int = 9222) -> bool:
    """Stop Chromium in a Daytona sandbox."""
    cmd = get_chrome_stop_command(port=port)
    try:
        if hasattr(sandbox, "exec"):
            res = sandbox.exec(f"bash -lc '{cmd}'")
            logger.info("Stopped Chrome in sandbox: %s", res)
            return True
        return False
    except Exception as exc:
        logger.error("Failed to stop Chrome in Daytona sandbox: %s", exc)
        return False


def verify_cdp_endpoint(cdp_url: str) -> dict[str, Any]:
    """Verify that a CDP endpoint is alive and return browser version metadata."""
    import urllib.request

    version_url = f"{cdp_url.rstrip('/')}/json/version"
    req = urllib.request.Request(version_url, headers={"User-Agent": "Daytona-CDP-Validator"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())
        user_agent = data.get("User-Agent", "")
        # Validate that it is regular Chrome/Chromium, not Electron
        is_chrome = "Chrome/" in user_agent or "Chromium/" in user_agent
        is_electron = "Electron/" in user_agent
        return {
            "status": "online",
            "browser": data.get("Browser", ""),
            "protocol_version": data.get("Protocol-Version", ""),
            "user_agent": user_agent,
            "is_valid_chrome": is_chrome and not is_electron,
        }
