#!/usr/bin/env python3
"""
HF Space Build Guard
====================
Validates everything BEFORE pushing to HuggingFace Space.
Prevents: broken Docker builds, binary file rejections, invalid README, failed health checks.

Exit codes:
  0 = all checks passed, safe to push
  1 = critical failure, DO NOT push
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

HF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hf-space")
errors = []
warnings = []


def check(name, func):
    print(f"{BOLD}Checking: {name}{RESET}...", end=" ")
    try:
        result = func()
        if result is True:
            print(f"{GREEN}PASS{RESET}")
        elif result is None:
            print(f"{YELLOW}WARN{RESET}")
        else:
            print(f"{RED}FAIL{RESET}")
    except Exception as e:
        print(f"{RED}FAIL{RESET} ({e})")
        errors.append(f"{name}: {e}")


def check_readme_frontmatter():
    """Validate README.md has correct HF YAML front matter."""
    readme_path = os.path.join(HF_DIR, "README.md")
    if not os.path.exists(readme_path):
        raise FileNotFoundError("README.md not found in hf-space/")

    with open(readme_path, encoding="utf-8") as f:
        content = f.read()

    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        raise ValueError("Missing YAML front matter (--- ... ---)")

    import yaml

    meta = yaml.safe_load(m.group(1))

    if not isinstance(meta, dict):
        raise ValueError("YAML front matter is not a mapping")

    allowed_colors = {"red", "yellow", "green", "blue", "indigo", "purple", "pink", "gray"}
    for key in ("colorFrom", "colorTo"):
        v = meta.get(key)
        if v not in allowed_colors:
            raise ValueError(f"{key}: {v!r} not in {sorted(allowed_colors)}")

    allowed_sdks = {"docker", "gradio", "streamlit", "static"}
    if meta.get("sdk") not in allowed_sdks:
        raise ValueError(f"sdk: {meta.get('sdk')!r} not in {sorted(allowed_sdks)}")

    if not meta.get("title"):
        raise ValueError("title is missing or empty")

    return True


def check_no_binary_files():
    """HF Spaces rejects binary files like .png, .jpg, .db."""
    forbidden = [".png", ".jpg", ".jpeg", ".gif", ".ico", ".db", ".duckdb", ".duckdb.wal"]
    found = []
    for root, dirs, files in os.walk(HF_DIR):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            if any(f.endswith(ext) for ext in forbidden):
                rel = os.path.relpath(os.path.join(root, f), HF_DIR)
                found.append(rel)
    if found:
        raise ValueError(f"Binary files found (HF will reject): {', '.join(found[:5])}")
    return True


def check_dockerfile_exists():
    """Dockerfile must exist and be valid."""
    path = os.path.join(HF_DIR, "Dockerfile")
    if not os.path.exists(path):
        raise FileNotFoundError("Dockerfile not found in hf-space/")
    with open(path) as f:
        content = f.read()
    if "EXPOSE" not in content:
        raise ValueError("Dockerfile missing EXPOSE directive")
    if "CMD" not in content and "ENTRYPOINT" not in content:
        raise ValueError("Dockerfile missing CMD or ENTRYPOINT")
    return True


def check_requirements():
    """requirements.hf.txt must exist and not contain Windows-only packages."""
    path = os.path.join(HF_DIR, "requirements.hf.txt")
    if not os.path.exists(path):
        raise FileNotFoundError("requirements.hf.txt not found in hf-space/")

    forbidden_pkgs = ["pywin32", "pyautogui", "opencv-python", "cupy"]
    with open(path) as f:
        for line in f:
            line = line.strip().lower()
            if line.startswith("#") or not line:
                continue
            for pkg in forbidden_pkgs:
                if pkg in line:
                    raise ValueError(f"Windows/forbidden package found: {pkg}")
    return True


def check_docker_available():
    """Check if Docker is available on this machine."""
    result = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
    return result.returncode == 0


def check_docker_build():
    """Actually build the Docker image to verify it works."""
    os.path.join(HF_DIR, "Dockerfile")

    if not check_docker_available():
        warnings.append(
            "Docker not available locally - skipping build check (will be validated on GitHub Actions)"
        )
        return None  # None = warning, not failure

    with tempfile.TemporaryDirectory() as tmpdir:
        # Copy hf-space to temp dir for isolated build
        for item in os.listdir(HF_DIR):
            if item == ".git":
                continue
            src = os.path.join(HF_DIR, item)
            dst = os.path.join(tmpdir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        result = subprocess.run(
            ["docker", "build", "-t", "hf-guard-test:latest", tmpdir],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            lines = result.stderr.strip().split("\n")
            error_tail = "\n".join(lines[-10:])
            raise RuntimeError(f"Docker build failed:\n{error_tail}")

    return True


def check_health_endpoint():
    """Run the Docker container and verify health endpoint."""
    container_name = "hf-guard-test-container"

    if not check_docker_available():
        warnings.append(
            "Docker not available locally - skipping health check (will be validated on GitHub Actions)"
        )
        return None  # None = warning, not failure

    try:
        # Stop any existing container
        subprocess.run(["docker", "rm", "-f", container_name],
                      capture_output=True, timeout=10)

        # Run container
        result = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                container_name,
                "-p",
                "7861:7860",
                "hf-guard-test:latest",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to start container: {result.stderr}")

        # Wait for startup
        import time

        time.sleep(5)

        # Test health endpoint
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "http://localhost:7861/healthz",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        status_code = result.stdout.strip()
        if status_code != "200":
            raise RuntimeError(f"Health check returned HTTP {status_code} (expected 200)")

        # Test root endpoint
        result = subprocess.run(
            ["curl", "-s", "http://localhost:7861/"], capture_output=True, text=True, timeout=10
        )

        if "AhmedETAP" not in result.stdout:
            raise RuntimeError("Root endpoint did not return expected content")

        return True

    finally:
        subprocess.run(["docker", "rm", "-f", container_name],
                      capture_output=True, timeout=10)


def check_no_secrets():
    """Ensure no secrets or tokens are in the hf-space directory."""
    secret_patterns = [
        r"hf_[A-Za-z0-9]{20,}",
        r"ghp_[A-Za-z0-9]{36}",
        r"github_pat_[A-Za-z0-9_]{50,}",
        r"sk-[A-Za-z0-9]{32,}",
        r"password\s*[:=]\s*['\"][^'\"]+['\"]",
        r"secret\s*[:=]\s*['\"][^'\"]+['\"]",
    ]

    for root, dirs, files in os.walk(HF_DIR):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            filepath = os.path.join(root, f)
            try:
                with open(filepath, encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                for pattern in secret_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        raise ValueError(
                            f"Potential secret found in {os.path.relpath(filepath, HF_DIR)}"
                        )
            except (UnicodeDecodeError, PermissionError):
                pass

    return True


def cleanup():
    """Clean up Docker test artifacts."""
    subprocess.run(["docker", "rm", "-f", "hf-guard-test-container"],
                  capture_output=True, timeout=10)
    subprocess.run(["docker", "rmi", "hf-guard-test:latest"],
                  capture_output=True, timeout=10)


def main():
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  HF Space Build Guard - Pre-Push Validation{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    try:
        check("README.md YAML front matter", check_readme_frontmatter)
        check("No binary files (HF rejects them)", check_no_binary_files)
        check("Dockerfile exists and is valid", check_dockerfile_exists)
        check("requirements.hf.txt (no Windows packages)", check_requirements)
        check("No secrets or tokens leaked", check_no_secrets)
        check("Docker image builds successfully", check_docker_build)
        check("Health endpoint responds HTTP 200", check_health_endpoint)
    finally:
        cleanup()

    print(f"\n{BOLD}{'='*60}{RESET}")

    if errors:
        print(f"\n{RED}{BOLD}FAILED - {len(errors)} critical error(s):{RESET}")
        for e in errors:
            print(f"  {RED}X{RESET} {e}")
        print(f"\n{RED}DO NOT PUSH - Fix errors first!{RESET}\n")
        sys.exit(1)
    else:
        print(f"\n{GREEN}{BOLD}ALL CHECKS PASSED - Safe to push to HuggingFace!{RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
