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

# System dependencies + create non-root user in a single RUN
# SonarCloud docker:S7031: merged consecutive RUN instructions to reduce layers
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
    && rm -rf /var/lib/apt/lists/* \
    # Create non-root user (UID 1000 as required by HF Spaces)
    && useradd -m -u 1000 user \
    && mkdir -p /app /tmp/cache /tmp/logs /tmp/data /tmp/cua_audit \
    && chown -R user:user /app /tmp

# Python dependencies — lightweight subset (no ML, no Celery, no Redis)
COPY hf-space/requirements.hf.txt /tmp/requirements.hf.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.hf.txt

# Install Chromium for Playwright (BrowserCUAExecutor — headless CUA on HF Space).
# On HF Spaces cpu-basic hardware, `--with-deps` can fail or exhaust disk.
# We install WITHOUT deps (the apt-get deps were already installed above:
# libnss3, libnspr4, libatk1.0-0, etc.) and make the install non-fatal.
# The chmod + chown ensure the non-root 'user' can read the browser binaries.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install chromium 2>&1 || \
    echo "⚠️ Playwright Chromium install failed — BrowserCUA will fall back to Format U" ; \
    chmod -R 755 /ms-playwright 2>/dev/null || true ; \
    chown -R user:user /ms-playwright 2>/dev/null || true

# Application code — copy only what hf-space/app.py needs
# SonarCloud S6504: Files are owned by root (not the non-root `user`) so the
# runtime container user can read+execute them but CANNOT modify them. This
# prevents a compromised app process from rewriting its own source code.
COPY --chown=root:root --chmod=go-w hf-space/app.py /app/app.py
COPY --chown=root:root --chmod=go-w compat.py /app/compat.py
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

# Environment mode (not a secret)
ENV ENVIRONMENT=${ENVIRONMENT:-production}

# Redis URL (empty = use in-memory fallback)
ENV REDIS_URL=

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:7860/healthz || exit 1

EXPOSE 7860

USER user

CMD ["python", "app.py"]
