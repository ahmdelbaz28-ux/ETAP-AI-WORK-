"""Pytest fixtures for boundary mismatch tests."""
import ast
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DIR = REPO_ROOT / "api"
UI_DIR = REPO_ROOT / "ui" / "src"
PROMPTS_DIR = REPO_ROOT / "prompts"
AGENTS_DIR = REPO_ROOT / "agents"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def api_files() -> list:
    """Return all Python files in api/ directory."""
    return list(API_DIR.glob("*.py"))


@pytest.fixture(scope="session")
def api_ts_content() -> str:
    """Return the content of ui/src/lib/api.ts."""
    api_ts = UI_DIR / "lib" / "api.ts"
    if api_ts.exists():
        return api_ts.read_text()
    return ""


@pytest.fixture(scope="session")
def prompt_files() -> list:
    """Return all prompt YAML files."""
    return list(PROMPTS_DIR.glob("*.yaml")) + list(PROMPTS_DIR.glob("*.yml"))


@pytest.fixture(scope="session")
def agent_files() -> list:
    """Return all agent Python files."""
    return list(AGENTS_DIR.glob("*.py"))
