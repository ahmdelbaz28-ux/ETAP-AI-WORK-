#!/usr/bin/env python3
"""Sync fixed Dockerfile to HF Space repo and trigger rebuild."""

import os
import shutil
import subprocess
import sys
import tempfile

HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
if not HF_TOKEN:
    print("ERROR: HF_TOKEN environment variable not set")
    print("Usage: $env:HF_TOKEN='hf_...'; python sync_hf.py")
    sys.exit(1)
REPO_URL = f"https://user:{HF_TOKEN}@huggingface.co/spaces/ahmdelbaz28/AhmedETAP-Platform"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))
TMP_DIR = tempfile.mkdtemp()

print(f"Cloning HF Space to {TMP_DIR} ...")
result = subprocess.run(
    ["git", "clone", "--depth", "1", REPO_URL, TMP_DIR], capture_output=True, text=True, timeout=120
)
if result.returncode != 0:
    print(f"Clone failed: {result.stderr}")
    sys.exit(1)
print("Clone OK")

# Copy fixed files
for f in ["Dockerfile", ".dockerignore"]:
    shutil.copy2(os.path.join(LOCAL_DIR, f), os.path.join(TMP_DIR, f))
    print(f"  Copied {f}")

# Commit and push
orig = os.getcwd()
os.chdir(TMP_DIR)

subprocess.run(
    ["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"],
    capture_output=True,
)
subprocess.run(["git", "config", "user.name", "github-actions[bot]"], capture_output=True)
subprocess.run(["git", "add", "-A"], capture_output=True)

result = subprocess.run(
    ["git", "commit", "-m", "fix(docker): remove inline comments from RUN/ENV to fix BUILD_ERROR"],
    capture_output=True,
    text=True,
)
print(f"Commit: {result.stdout.strip()} {result.stderr.strip()}")

result = subprocess.run(
    ["git", "push", REPO_URL, "main"], capture_output=True, text=True, timeout=120
)
print(f"Push stdout: {result.stdout[-800:]}")
if result.stderr:
    print(f"Push stderr: {result.stderr[-800:]}")

os.chdir(orig)
shutil.rmtree(TMP_DIR, ignore_errors=True)
print("Done - HF Space rebuild should be triggered automatically")
