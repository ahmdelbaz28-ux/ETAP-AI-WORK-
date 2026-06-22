"""Fixtures for agent evaluation tests."""
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def repo_root():
    return REPO_ROOT


@pytest.fixture(scope="session")
def prompts_dir():
    return REPO_ROOT / "prompts"


@pytest.fixture(scope="session")
def agents_dir():
    return REPO_ROOT / "agents"
