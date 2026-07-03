FROM python:3.13-slim

LABEL maintainer="Eng. Ahmed Elbaz <ahmdelbaz28@gmail.com>"
LABEL description="AhmedETAP - Enterprise Engineering Intelligence Platform"
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

# Python dependencies
COPY requirements.hf.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.hf.txt

# Application code — copy specific directories instead of recursive COPY
# (SonarCloud S6470: avoid recursive COPY . . which can inadvertently
# add sensitive data). We copy only what app.py needs at runtime.
COPY --chown=user:user app.py .
COPY --chown=user:user api/ ./api/
COPY --chown=user:user agents/ ./agents/  # NOSONAR — S6470: .dockerignore excludes secrets
COPY --chown=user:user core/ ./core/
COPY --chown=user:user core_model/ ./core_model/
COPY --chown=user:user engine/ ./engine/
COPY --chown=user:user fault_analysis/ ./fault_analysis/
COPY --chown=user:user load_flow/ ./load_flow/
COPY --chown=user:user relays/ ./relays/
COPY --chown=user:user services/ ./services/
COPY --chown=user:user utils/ ./utils/
COPY --chown=user:user curves/ ./curves/
COPY --chown=user:user scada_model/ ./scada_model/
COPY --chown=user:user digital_twin/ ./digital_twin/
COPY --chown=user:user guards/ ./guards/
COPY --chown=user:user knowledge/ ./knowledge/
COPY --chown=user:user reporting/ ./reporting/
COPY --chown=user:user integrations/ ./integrations/
COPY --chown=user:user security/ ./security/
COPY --chown=user:user etap_integration/ ./etap_integration/
COPY --chown=user:user ai_context_engine/ ./ai_context_engine/
COPY --chown=user:user ml/ ./ml/
COPY --chown=user:user network_solver/ ./network_solver/
COPY --chown=user:user monitoring/ ./monitoring/
COPY --chown=user:user visualization/ ./visualization/
COPY --chown=user:user copilot/ ./copilot/
COPY --chown=user:user prompts/ ./prompts/
COPY --chown=user:user schemas/ ./schemas/
COPY --chown=user:user config/ ./config/

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
ENV TRANSFORMERS_CACHE=/tmp/cache
ENV TORCH_HOME=/tmp/cache

# Database path — default to SQLite in /tmp (writable on HF Spaces).
# IMPORTANT: this is only a fallback. If the HF Space has a DATABASE_URL secret
# set (e.g. pointing to Neon/Supabase Postgres), that secret OVERRIDES this
# default because HF Space secrets are injected at runtime, not build time.
ENV DATABASE_URL=${DATABASE_URL:-sqlite+aiosqlite:////tmp/data/etap_platform.db}

# Security v2.1.5 (SonarCloud S6472): Secrets (JWT_SECRET_KEY,
# ENGINEERING_SERVICE_API_KEY) are NOT declared as ENV here — baking them
# into image layers leaks them via `docker history`. They are injected at
# RUNTIME via HF Space Secrets, Docker --secret, or Kubernetes Secrets.

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
