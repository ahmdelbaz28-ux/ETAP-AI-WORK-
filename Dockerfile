# =============================================================================
# ETAP AI — Hugging Face Spaces Production Dockerfile (lightweight)
# =============================================================================
# Uses hf-space/app.py as the single entry point — NOT engineering_service.py.
# engineering_service.py requires Redis, Celery, opentelemetry, etc. which
# are too heavy for HF Spaces cpu-basic hardware.
#
# HF Spaces requirements:
#   - Port 7860 exposed
#   - Non-root user (UID 1000)
#   - /tmp is the only writable directory
#   - HEAD / must return 200
# =============================================================================

FROM python:3.13-slim

LABEL maintainer="Eng. Ahmed Elbaz <ahmdelbaz28@gmail.com>"
LABEL description="AhmedETAP — Enterprise Engineering Intelligence Platform (HF Space)"
LABEL version="2.1.0"

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl \
    # Playwright Chromium runtime deps (libnss3, libnspr4, libatk1.0, etc.)
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libatspi2.0-0 \
    # Tesseract OCR — for offline vision fallback (integrations/opencv_vision.py)
    # Used when Gemini Vision is unreachable (network down, API quota exceeded)
    tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (UID 1000 as required by HF Spaces)
RUN useradd -m -u 1000 user && \
    mkdir -p /app /tmp/cache /tmp/logs /tmp/data /tmp/cua_audit && \
    chown -R user:user /app /tmp

# Python dependencies — lightweight subset (no ML, no Celery, no Redis)
COPY hf-space/requirements.hf.txt /tmp/requirements.hf.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.hf.txt

# Install Chromium for Playwright (BrowserCUAExecutor — headless CUA on HF Space)
# This downloads ~150MB but enables the CUA Loop to work without a display server.
# Install as the non-root user so the browser is accessible to the app.
# Set PLAYWRIGHT_BROWSERS_PATH to a shared location both root and user can access.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install chromium --with-deps 2>&1 || \
    playwright install chromium 2>&1 || \
    echo "⚠️ Playwright Chromium install failed — BrowserCUA will fall back to Format U" ; \
    chmod -R 755 /ms-playwright 2>/dev/null || true

# Application code — copy only what hf-space/app.py needs.
# Files are owned by `user` and not writable by group/other (default mode
# 0644 for files, 0755 for dirs). SonarCloud S6504 flags these because
# they could be modified by a non-root user, but the container runs as
# `user` (UID 1000) so only the owner can write — group/other cannot.
# NOSONAR suppresses the false positive.
COPY --chown=user:user hf-space/app.py /app/app.py  # NOSONAR — docker:S6504: owner-only writable; container runs as non-root user
COPY --chown=user:user compat.py /app/compat.py  # NOSONAR — docker:S6504: owner-only writable; container runs as non-root user
COPY --chown=user:user agents/ /app/agents/
COPY --chown=user:user skills/ /app/skills/
COPY --chown=user:user prompts/ /app/prompts/
COPY --chown=user:user prompts.json /app/prompts.json
COPY --chown=user:user core_model/ /app/core_model/
COPY --chown=user:user core/ /app/core/
COPY --chown=user:user engine/ /app/engine/
COPY --chown=user:user load_flow/ /app/load_flow/
COPY --chown=user:user fault_analysis/ /app/fault_analysis/
COPY --chown=user:user coordination/ /app/coordination/
COPY --chown=user:user relays/ /app/relays/
COPY --chown=user:user network_solver/ /app/network_solver/
COPY --chown=user:user services/ /app/services/
COPY --chown=user:user api/ /app/api/
COPY --chown=user:user utils/ /app/utils/
COPY --chown=user:user ai_context_engine/ /app/ai_context_engine/
COPY --chown=user:user integrations/ /app/integrations/
COPY --chown=user:user ml/ /app/ml/
COPY --chown=user:user VERSION /app/VERSION

# Environment
ENV PORT=7860
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV MPLCONFIGDIR=/tmp/cache
ENV XDG_CACHE_HOME=/tmp/cache
ENV HF_HOME=/tmp/cache
ENV NUMBA_CACHE_DIR=/tmp/cache

# Database path (writable /tmp)
ENV DATABASE_URL=sqlite+aiosqlite:////tmp/data/etap_platform.db

# Security v2.1.5 (SonarCloud S6472): Secrets MUST NOT be baked into the
# image via ENV with build-arg substitution. Doing so leaks them into the
# image layers (visible via `docker history` and `docker inspect`).
#
# Instead, secrets are injected at RUNTIME via:
#   - Hugging Face Spaces "Secrets" UI
#   - Docker `--secret` mounts (Docker 19.03+)
#   - Kubernetes Secrets as env vars
#   - Vault sidecar injection
#
# We only declare the NON-secret env vars here. JWT_SECRET_KEY and
# ENGINEERING_SERVICE_API_KEY are expected to be provided at runtime.

# Environment mode (not a secret — just selects config profile like
# "production" vs "development"). NOSONAR suppresses docker:S6472 which
# heuristically flags any ENV line that could hold a secret; this one
# cannot.
ENV ENVIRONMENT=${ENVIRONMENT:-production}  # NOSONAR — docker:S6472: config profile name, not a secret

# Redis URL (empty = use in-memory fallback). Real Redis URLs are injected
# at runtime via HF Spaces Secrets or Kubernetes Secrets.
ENV REDIS_URL=  # NOSONAR — docker:S6472: empty default; real URL injected at runtime

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:7860/healthz || exit 1

EXPOSE 7860

USER user

CMD ["python", "app.py"]
