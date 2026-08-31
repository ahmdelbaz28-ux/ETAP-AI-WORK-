"""WP5 (Iron Loop) — prompt manifest-first loading and consistency tests.

DoD coverage:
- Loading the ``etap_engineer_agent`` handle resolves to the v2 prompt via
  the prompts.json manifest (manifest-first beats filename patterns).
- scripts/check_prompt_consistency.py exits 0.
- scripts/sync_to_langfuse.py pushes exactly the manifest handles (v1/ghost
  files are never uploaded), verified with a stubbed httpx transport.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.prompt_loader import get_system_prompt


def _system_message(path: Path) -> str:
    import yaml

    parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for msg in parsed.get("messages", []):
        if msg.get("role") == "system":
            return msg.get("content", "")
    return ""


def test_etap_engineer_handle_loads_v2_via_manifest() -> None:
    v2_path = ROOT / "prompts" / "etap_engineer_agent_v2.yaml"
    assert v2_path.is_file(), "v2 prompt file must exist"
    loaded = get_system_prompt("etap_engineer_agent")
    assert loaded, "handle etap_engineer_agent must resolve locally"
    expected = _system_message(v2_path)
    assert loaded.strip() == expected.strip(), (
        "handle 'etap_engineer_agent' must resolve to the v2 system message "
        "(manifest-first loading)"
    )


def test_check_prompt_consistency_exit_zero() -> None:
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_prompt_consistency.py")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_sync_to_langfuse_pushes_only_manifest_handles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = json.loads((ROOT / "prompts.json").read_text(encoding="utf-8"))
    expected_handles = set(manifest["prompts"].keys())

    posted: list[dict[str, Any]] = []

    class _Resp:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {"data": []}

    stub_httpx = types.ModuleType("httpx")
    stub_httpx.get = lambda *a, **k: _Resp()

    def _fake_post(url: str, json: Any = None, **kwargs: Any) -> _Resp:
        posted.append({"url": url, "json": json})
        return _Resp()

    stub_httpx.post = _fake_post
    monkeypatch.setitem(sys.modules, "httpx", stub_httpx)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")

    spec = importlib.util.spec_from_file_location(
        "_sync_to_langfuse_under_test", ROOT / "scripts" / "sync_to_langfuse.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with pytest.raises(SystemExit) as exc_info:
        spec.loader.exec_module(module)
    assert exc_info.value.code == 0, "offline stubbed sync must complete cleanly"

    pushed_names = [p["json"]["name"] for p in posted if p.get("json")]
    assert set(pushed_names) == expected_handles, (
        "sync must push exactly the manifest handles — no filename-derived "
        "ghosts such as etap_engineer_agent (v1)"
    )
    # The engineer handle must carry the v2 body.
    engineer = next(p for p in posted if p["json"]["name"] == "etap_engineer_agent")
    messages = engineer["json"]["prompt"]
    system_msgs = [m["content"] for m in messages if m.get("role") == "system"]
    v2_system = _system_message(ROOT / "prompts" / "etap_engineer_agent_v2.yaml")
    assert system_msgs and system_msgs[0].strip() == v2_system.strip(), (
        "pushed etap_engineer_agent prompt must be the v2 system message"
    )
