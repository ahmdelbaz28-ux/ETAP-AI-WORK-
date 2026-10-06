import os
import re
from pathlib import Path

import pytest

try:
    from importlib import metadata as importlib_metadata
except ImportError:
    import importlib_metadata


ALLOWED_LICENSES_PATTERNS = [
    re.compile(r"mit", re.IGNORECASE),
    re.compile(r"apache", re.IGNORECASE),
    re.compile(r"bsd", re.IGNORECASE),
    re.compile(r"isc", re.IGNORECASE),
    re.compile(r"python software foundation", re.IGNORECASE),
    re.compile(r"psf", re.IGNORECASE),
    re.compile(r"lgpl", re.IGNORECASE),
    re.compile(r"mpl", re.IGNORECASE),
    re.compile(r"unlicense", re.IGNORECASE),
    re.compile(r"public domain", re.IGNORECASE),
    re.compile(r"cc0", re.IGNORECASE),
]

DISALLOWED_LICENSES_PATTERNS = [
    re.compile(r"\bagpl\b", re.IGNORECASE),
    re.compile(r"affero", re.IGNORECASE),
    re.compile(r"\bsspl\b", re.IGNORECASE),
]


def test_root_license_file_exists_and_valid():
    """Verify that root repository contains a valid open-source MIT LICENSE file."""
    repo_root = Path(__file__).resolve().parent.parent
    license_file = repo_root / "LICENSE"

    assert license_file.exists(), "LICENSE file must exist in repository root"
    content = license_file.read_text(encoding="utf-8")
    assert "MIT License" in content, "LICENSE must explicitly declare MIT License"
    assert "Eng. Ahmed Elbaz" in content, "LICENSE must include author attribution"


def test_pyproject_toml_license_declared():
    """Verify that pyproject.toml declares the proper project license."""
    repo_root = Path(__file__).resolve().parent.parent
    pyproject_file = repo_root / "pyproject.toml"

    assert pyproject_file.exists(), "pyproject.toml must exist"
    content = pyproject_file.read_text(encoding="utf-8")
    assert "MIT" in content or "license" in content.lower(), (
        "pyproject.toml must declare a recognized license"
    )


def test_requirements_dependencies_license_compliance():
    """Verify that dependencies declared in requirements.txt have compliant open source licenses."""
    repo_root = Path(__file__).resolve().parent.parent
    req_file = repo_root / "requirements.txt"

    assert req_file.exists(), "requirements.txt must exist"
    lines = req_file.read_text(encoding="utf-8").splitlines()

    package_names = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = re.split(r"[~=<>!;\[]", line)[0].strip()
        if pkg:
            package_names.append(pkg)

    assert len(package_names) > 0, "requirements.txt must define production dependencies"

    checked_count = 0
    non_compliant = []

    for pkg_name in package_names:
        try:
            dist = importlib_metadata.distribution(pkg_name)
        except importlib_metadata.PackageNotFoundError:
            continue

        raw_license = str(
            dist.metadata.get("License")
            or dist.metadata.get("License-Expression")
            or dist.metadata.get("License-File")
            or ""
        )
        classifiers = dist.metadata.get_all("Classifier") or []
        license_classifiers = [c for c in classifiers if c.startswith("License ::")]

        has_permissive_classifier = any(
            any(p.search(c) for p in ALLOWED_LICENSES_PATTERNS)
            for c in license_classifiers
        )
        if has_permissive_classifier:
            has_agpl_classifier = any(
                any(p.search(c) for p in DISALLOWED_LICENSES_PATTERNS)
                for c in license_classifiers
            )
            if has_agpl_classifier:
                non_compliant.append((pkg_name, raw_license, license_classifiers))
        else:
            # Fall back to raw_license string
            has_allowed = any(p.search(raw_license) for p in ALLOWED_LICENSES_PATTERNS)
            has_disallowed = any(p.search(raw_license) for p in DISALLOWED_LICENSES_PATTERNS)
            if not has_allowed or has_disallowed:
                non_compliant.append((pkg_name, raw_license, license_classifiers))

        checked_count += 1

    assert len(non_compliant) == 0, f"Found non-compliant licensed packages: {non_compliant}"
    assert checked_count > 5, f"Expected to verify installed packages, checked {checked_count}"
