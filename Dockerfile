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
LABEL build.rebuild="full"

WORKDIR /app

# System dependencies + create non-root user in a single RUN
# SonarCloud docker:S7031: merged consecutive RUN instructions to reduce layers
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl g++ gcc \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
    libcairo2 libcups2 libdrm2 libgbm1 libnspr4 libnss3 \
    libpango-1.0-0 libxcomposite1 libxdamage1 libxfixes3 \
    libxkbcommon0 libxrandr2 \
    tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 user \
    && mkdir -p /app /tmp/cache /tmp/logs /tmp/data /tmp/cua_audit \
    && chown -R user:user /app /tmp

# Python dependencies — lightweight subset (no ML, no Celery, no Redis).
# requirements.hf.txt is version-locked (~=) so this install can stay
# binary-only (SonarCloud docker:S8544).
# NOTE: pre-commit hooks are NOT installed in the Docker image.
COPY hf-space/requirements.hf.txt /tmp/requirements.hf.txt
RUN pip install --no-cache-dir --only-binary :all: --upgrade pip==25.0.1 && \
    pip install --no-cache-dir --only-binary :all: \
        --requirement /tmp/requirements.hf.txt

# Install Chromium for Playwright (BrowserCUAExecutor — headless CUA on HF Space).
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install chromium 2>&1 || \
    echo "Playwright Chromium install failed — BrowserCUA will fall back to Format U" ; \
    chmod -R 755 /ms-playwright 2>/dev/null || true ; \
    chown -R user:user /ms-playwright 2>/dev/null || true

# Application code — copy only what hf-space/app.py needs
# Source files owned by root (read-only) for security.
COPY --chown=root:root --chmod=go-w hf-space/app.py /app/app.py
COPY --chown=root:root --chmod=go-w compat.py /app/compat.py
COPY --chown=root:root --chmod=go-w agents/ /app/agents/
# NOTE: skills/ is NOT copied to the HF Space Docker image.
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

# UI static files (Vite-built React app, served at root / by app.py)
# Build the UI first: cd ui && npm run build && cp -r dist ../ui-dist/
COPY --chown=user:user ui-dist/ /app/ui-dist/

# Environment — runtime configuration (NOT secrets).
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

# Environment mode (not a secret)
ENV ENVIRONMENT=${ENVIRONMENT:-production}

# Redis URL — empty default means in-memory fallback (development mode).
ENV REDIS_URL=

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:7860/healthz || exit 1

EXPOSE 7860

# Use numeric UID (1000) per HF Spaces recommendation
USER 1000

CMD ["python", "app.py"]
