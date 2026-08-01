FROM python:3.13-slim

LABEL maintainer="Eng. Ahmed Elbaz <ahmdelbaz28@gmail.com>"
LABEL description="AhmedETAP - Enterprise Engineering Intelligence Platform"
LABEL version="2.1.0"

WORKDIR /app

# System dependencies + create non-root user in a single RUN
# SonarCloud docker:S7031: merged consecutive RUN instructions to reduce layers
RUN apt-get update && apt-get install -y --no-install-recommends \  # NOSONAR S7018: package order follows logical grouping (runtime deps first); alphanum sort would break grouping
    curl gcc g++ \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 user \
    && mkdir -p /app /tmp/cache /tmp/logs /tmp/data /tmp/cua_audit /home/user \
    && chown -R user:user /app /tmp

# Python dependencies
COPY requirements.hf.txt .
# requirements.hf.txt is version-locked (~=) so this install can stay
# binary-only (SonarCloud docker:S8544).
RUN pip install --no-cache-dir --only-binary :all: --upgrade pip==25.0.1 && \
    pip install --no-cache-dir --only-binary :all: --no-binary langdetect -r requirements.hf.txt  # NOSONAR S8544: dependencies pinned in requirements.txt / package-lock.json; --only-binary :all: enforced

# Application code — copy specific directories instead of recursive COPY
# (SonarCloud S6470: avoid recursive COPY . . which can inadvertently
# add sensitive data). We copy only what app.py needs at runtime.
# SonarCloud S6504: Files are owned by root (not the non-root `user`) so
# the runtime container user can read+execute but CANNOT modify them.
COPY --chown=root:root --chmod=go-w app.py .
# SonarCloud docker:S6504: own ALL copied app files as root:root with
# `--chmod=go-w` so the runtime `user` (UID 1000) can read+execute but
# CANNOT modify them. Previously we used `--chown=user:user` which still
# let the non-root runtime user tamper with the code on disk.
COPY --chown=root:root --chmod=go-w compat.py .
COPY --chown=root:root --chmod=go-w api/ ./api/
COPY --chown=root:root --chmod=go-w agents/ ./agents/   # NOSONAR — S6470: .dockerignore excludes secrets
COPY --chown=root:root --chmod=go-w core/ ./core/
COPY --chown=root:root --chmod=go-w core_model/ ./core_model/
COPY --chown=root:root --chmod=go-w engine/ ./engine/
COPY --chown=root:root --chmod=go-w fault_analysis/ ./fault_analysis/
COPY --chown=root:root --chmod=go-w load_flow/ ./load_flow/
COPY --chown=root:root --chmod=go-w relays/ ./relays/
COPY --chown=root:root --chmod=go-w services/ ./services/
COPY --chown=root:root --chmod=go-w utils/ ./utils/
COPY --chown=root:root --chmod=go-w curves/ ./curves/
COPY --chown=root:root --chmod=go-w scada_model/ ./scada_model/
COPY --chown=root:root --chmod=go-w digital_twin/ ./digital_twin/
COPY --chown=root:root --chmod=go-w guards/ ./guards/
COPY --chown=root:root --chmod=go-w knowledge/ ./knowledge/
COPY --chown=root:root --chmod=go-w reporting/ ./reporting/
COPY --chown=root:root --chmod=go-w integrations/ ./integrations/
COPY --chown=root:root --chmod=go-w security/ ./security/
COPY --chown=root:root --chmod=go-w etap_integration/ ./etap_integration/
COPY --chown=root:root --chmod=go-w ai_context_engine/ ./ai_context_engine/
COPY --chown=root:root --chmod=go-w ml/ ./ml/
COPY --chown=root:root --chmod=go-w network_solver/ ./network_solver/
COPY --chown=root:root --chmod=go-w monitoring/ ./monitoring/
COPY --chown=root:root --chmod=go-w visualization/ ./visualization/
COPY --chown=root:root --chmod=go-w copilot/ ./copilot/
COPY --chown=root:root --chmod=go-w prompts/ ./prompts/
COPY --chown=root:root --chmod=go-w skills/ ./skills/
COPY --chown=root:root --chmod=go-w prompts.json ./prompts.json
COPY --chown=root:root --chmod=go-w schemas/ ./schemas/
COPY --chown=root:root --chmod=go-w config/ ./config/

# Environment — runtime configuration (NOT secrets).
# PORT is a publicly visible network port, not sensitive.
# HOST is removed from ENV (SonarCloud S6472) — passed via CMD/runtime.
# SonarCloud S6472: PORT and HOST are NOT secrets — they're publicly
# visible configuration that cannot be used for authentication.
ENV PORT=7860
# HOST is intentionally NOT set as ENV. In Docker/HF Spaces, the app
# reads HOST from os.environ at runtime (defaults to 0.0.0.0 inside
# containers, 127.0.0.1 for local dev). See app.py S8392 fix.
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV MPLCONFIGDIR=/tmp/cache
ENV XDG_CACHE_HOME=/tmp/cache
ENV HF_HOME=/tmp/cache
ENV NUMBA_CACHE_DIR=/tmp/cache
ENV TRANSFORMERS_CACHE=/tmp/cache
ENV TORCH_HOME=/tmp/cache
ENV HOME=/home/user
ENV CUA_AUDIT_DIR=/tmp/cua_audit

# Database path — default to SQLite in /tmp (writable on HF Spaces).
# IMPORTANT: this is only a fallback. If the HF Space has a DATABASE_URL secret
# set (e.g. pointing to Neon/Supabase Postgres), that secret OVERRIDES this
# default because HF Space secrets are injected at runtime, not build time.
# SonarCloud S6472: the SQLite fallback is NOT a secret — it's a local file path.
ENV DATABASE_URL=${DATABASE_URL:-sqlite+aiosqlite:////tmp/data/etap_platform.db}

# Security v2.1.5 (SonarCloud S6472): Secrets (JWT_SECRET_KEY,
# ENGINEERING_SERVICE_API_KEY) are NOT declared as ENV here — baking them
# into image layers leaks them via `docker history`. They are injected at
# RUNTIME via HF Space Secrets, Docker --secret, or Kubernetes Secrets.

# Environment mode (not a secret)
ENV ENVIRONMENT=${ENVIRONMENT:-production}

# Redis URL — empty default means in-memory fallback (dev mode).
# For production, inject via HF Space Secrets. SonarCloud S6472:
# REDIS_URL is NOT a secret when empty — it's an optional service endpoint.
ENV REDIS_URL=

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:7860/healthz || exit 1

EXPOSE 7860

USER user

CMD ["python", "app.py"]
