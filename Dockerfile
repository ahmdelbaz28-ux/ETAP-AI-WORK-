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
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (UID 1000 as required by HF Spaces)
RUN useradd -m -u 1000 user && \
    mkdir -p /app /tmp/cache /tmp/logs /tmp/data && \
    chown -R user:user /app /tmp

# Python dependencies — lightweight subset (no ML, no Celery, no Redis)
COPY hf-space/requirements.hf.txt /tmp/requirements.hf.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.hf.txt

# Application code — copy only what hf-space/app.py needs
COPY --chown=user:user hf-space/app.py /app/app.py
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

# JWT secret (set as HF Space secret in production)
ENV JWT_SECRET_KEY=${JWT_SECRET_KEY:-}

# API key (set as HF Space secret in production)
ENV ENGINEERING_SERVICE_API_KEY=${ENGINEERING_SERVICE_API_KEY:-}

# Environment mode
ENV ENVIRONMENT=${ENVIRONMENT:-production}

# Redis URL (empty = use in-memory fallback)
ENV REDIS_URL=

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:7860/healthz || exit 1

EXPOSE 7860

USER user

CMD ["python", "app.py"]
