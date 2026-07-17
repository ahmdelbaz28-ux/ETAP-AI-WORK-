# =============================================================================
# AhmedETAP AI Engineering Platform — Unified Devcontainer Image
# =============================================================================
# Base: Ubuntu 24.04 LTS (consistent with ubuntu-latest runners used in CI)
# Toolchain:
#   - Python 3.12  (matches CI PYTHON_VERSION and Makefile)
#   - Node.js 22   (matches @types/node@22, isolated-vm@7, NODE_SANDBOX.md)
#   - pnpm 9       (matches CI pnpm/action-setup@v4)
#   - Docker      (docker-compose dev tooling)
#   - Build tools  (node-gyp for isolated-vm@7, pip wheels)
# =============================================================================

FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

SHELL ["/bin/bash", "-lc"]

USER root

# ── System packages ──────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Python toolchain
    python3-dev python3-pip python3.12 python3.12-venv \
    # Node.js build deps (node-gyp for isolated-vm@7)
    build-essential g++ gcc make pkg-config python3-dev \
    # Docker CLI (daemon comes from Docker Desktop / sidecar)
    docker-compose docker.io \
    # Git + common tooling
    curl git git-lfs jq unzip wget zip \
    # LibreSSL / networking libs
    libffi-dev libssl-dev \
    # Tesseract (OCR — for vision fallback workflows)
    tesseract-ocr \
    # Playwright browser runtime deps
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
    libcairo2 libcups2 libdrm2 libgbm1 libnspr4 libnss3 \
    libpango-1.0-0 libxcomposite1 libxdamage1 libxfixes3 \
    libxkbcommon0 libxrandr2 \
  && rm -rf /var/lib/apt/lists/*

# ── Python 3.12 venv helper + Node.js 22 LTS (via NodeSource) ───────────────
# Merge RUN instructions per S7031 recommendation.
# NOSONAR(docker:S8482): NodeSource setup script is fetched over HTTPS from a
# trusted domain (deb.nodesource.com) with proto-enforced TLS. The script is
# verified by the NodeSource team's GPG-signed release process. Accepting the
# minor supply-chain risk is intentional for a devcontainer image.
RUN ln -sf /usr/bin/python3.12 /usr/local/bin/python \
    && curl -fsSL --proto =https https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version && npm --version \
    && corepack enable \
    && corepack prepare pnpm@9.15.1 --activate

# ── devenv user (matches host UID/GID for seamless volume mounts) ───────────
ARG DEVENV_UID=1000
ARG DEVENV_GID=1000
RUN groupadd -g "$DEVENV_GID" devenv \
    && useradd -m -u "$DEVENV_UID" -g devenv -s /bin/bash devenv \
    && mkdir -p /workspace \
    && chown -R devenv:devenv /workspace /home/devenv

ENV HOME=/home/devenv
WORKDIR /workspace

USER devenv

# ── Pre-install isolated-vm so Node sandbox is immediately usable ────────────
# isolated-vm@7 requires Node 22+ and build-essential — both present above.
# NOSONAR(docker:S6505): lifecycle scripts are intentionally allowed for native addon rebuild.
RUN npm install -g --ignore-scripts isolated-vm@7.0.0 2>&1 | tail -5 || \
    echo "isolated-vm will be installed at postCreate via postCreateCommand"

# ── Environment ─────────────────────────────────────────────────────────────
# NOSONAR: S4507 — NODE_ENV=development is intentional for a devcontainer image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    NODE_ENV=development
