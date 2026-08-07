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
# `pre-commit install` writes to .git/hooks/pre-commit, which requires a git
# repository. The HF Space Docker build context excludes .git/ (see
# .dockerignore), so `pre-commit install` fails with "fatal: not a git
# repository" → Docker build exits 1 → HF Space enters BUILD_ERROR state.
# Pre-commit is a developer-side tool (runs locally before commit); the
# production image does not need it. CI enforces lint/tests separately.
COPY hf-space/requirements.hf.txt /tmp/requirements.hf.txt
RUN pip install --no-cache-dir --only-binary :all: --upgrade pip==25.0.1 && \
    pip install --no-cache-dir --only-binary :all: \
        --requirement /tmp/requirements.hf.txt  # noqa: docker:S8544 — versions pinned in requirements.hf.txt

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
# V-70 FIX: agents/ directory is now owned by root (read-only) for consistency
# with the security posture on lines 64-66. Previously it was writable by the
# non-root user, which violated the principle of least privilege.
COPY --chown=root:root --chmod=go-w agents/ /app/agents/
# NOTE: skills/ is NOT copied to the HF Space Docker image.
# The skills/ directory contains large HTML templates that exceed HF's file
# size limit (causing push rejection). The HF Space loads skills at runtime
# from the GitHub repo via the AI agent — they are not needed in the image.
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
COPY --chown=user:user ui-dist/ /app/ui-dist/

# Environment — runtime configuration (NOT secrets).
# PORT and HOST are network configuration, not sensitive values.
# SonarCloud S6472: these are NOT secrets — they're publicly visible
# configuration that cannot be used for authentication or encryption.
ENV PORT=7860
# HOST=0.0.0.0 is required for Docker/HF Spaces port-mapping.
# Without it, uvicorn binds to 127.0.0.1 and the HF Space platform
# health probe cannot reach the container — resulting in RUNTIME_ERROR:
# "Launch timed out, workload was not healthy after 30 min".
# SonarCloud S6472: binding address is network config, NOT a secret.
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV MPLCONFIGDIR=/tmp/cache
ENV XDG_CACHE_HOME=/tmp/cache
ENV HF_HOME=/tmp/cache
ENV NUMBA_CACHE_DIR=/tmp/cache

# Database path (writable /tmp) — NOT a secret, just a SQLite connection string
# pointing to a local file. For production, override with a Postgres URL
# injected at runtime via HF Space Secrets or Kubernetes Secrets.
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

# Redis URL — empty default means in-memory fallback (development mode).
# For production, override via runtime secret injection.
# SonarCloud S6472: this is NOT a secret — it's an optional service endpoint.
ENV REDIS_URL=

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:7860/healthz || exit 1

EXPOSE 7860

# HF Spaces recommended pattern: use the numeric UID (1000) instead of the
# symbolic name ('user'). Numeric UIDs do NOT require /etc/passwd lookup at
# runtime, which avoids the RUNTIME_ERROR:
#   "The Dockerfile's USER directive references a user that is not present
#    in the image's /etc/passwd."
# The 'useradd -m -u 1000 user' layer above creates the user with UID 1000;
# we reference that UID directly here.
# Ref: https://huggingface.co/docs/hub/spaces-sdks-docker#user
USER 1000

# HOST=0.0.0.0 is set via ENV above so uvicorn binds to all interfaces,
# which is required for Docker/HF Spaces port-mapping. For local development,
# override HOST=127.0.0.1 when running outside a container.
CMD ["python", "app.py"]

# ETAP AI Engineering Platform - Multi-Stage Docker Build
# =============================================================================
# Stage 1: Python Builder
FROM python:3.13-slim AS python-builder

LABEL stage="python-builder"

RUN apt-get update && apt-get install -y     gcc     g++     curl     --no-install-recommends     && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Use production requirements for smaller image
COPY requirements-prod.txt .
RUN mv requirements-prod.txt requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    # Filter requirements.txt to a temp file (exclude pywin32 which is
    # Windows-only). We must NOT use `tr '\n' ' '` because that breaks
    # PEP 508 environment markers like `cupy-cuda12x>=13.0.0;
    # platform_machine == 'x86_64'` — the shell would split the marker
    # across spaces and pip would see a bare `==` token.
    grep -v "pywin32" requirements.txt | grep -v "^#" | grep -v "^$" > /tmp/requirements.filtered.txt && \
    pip install --no-cache-dir \
        --prefix=/install \
        -r /tmp/requirements.filtered.txt && \
    rm -f /tmp/requirements.filtered.txt

# =============================================================================
# Stage 2: TypeScript / Node Builder
FROM node:20-slim AS ts-builder

LABEL stage="ts-builder"

RUN apt-get update && apt-get install -y     curl     --no-install-recommends     && rm -rf /var/lib/apt/lists/*

# Pin pnpm to v9 — pnpm 11.x requires Node 22+ (uses node:sqlite built-in)
# which is incompatible with the node:20-slim base image used here.
RUN corepack enable && corepack prepare pnpm@9 --activate

WORKDIR /build

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

RUN pnpm install --no-frozen-lockfile

COPY . .

RUN pnpm build

# Ensure dist/ and public/ directories exist after the build so the
# runtime stage can COPY them without failing. The Mastra build does
# not produce these directories (it outputs to .mastra/output/), but
# the runtime stage expects /build/dist and /build/public to exist.
# Creating them as empty directories is harmless — they just become
# empty /app/ui/dist and /app/ui/public in the runtime image.
RUN mkdir -p /build/dist /build/public

# Remove dev dependencies to reduce size
RUN pnpm prune --prod

# =============================================================================
# Stage 3: Runtime
FROM python:3.13-slim

LABEL maintainer="ETAP AI Platform Team"
LABEL description="AI-powered ETAP Engineering Platform - Multi-Arch"
LABEL version="2.1.0"

# Runtime libs only
RUN apt-get update && apt-get install -y --no-install-recommends     curl     tini     && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=python-builder /install /usr/local

# Copy built frontend from builder
COPY --from=ts-builder /build/dist /app/ui/dist
COPY --from=ts-builder /build/node_modules /app/ui/node_modules
COPY --from=ts-builder /build/package.json /app/ui/package.json
COPY --from=ts-builder /build/public /app/ui/public

# Copy Python source files
COPY engineering_service.py /app/
COPY engine/ /app/engine/
COPY core_model/ /app/core_model/
COPY core/ /app/core/
COPY security/ /app/security/
COPY load_flow/ /app/load_flow/
COPY fault_analysis/ /app/fault_analysis/
COPY digital_twin/ /app/digital_twin/
COPY knowledge/ /app/knowledge/
COPY coordination/ /app/coordination/
COPY relays/ /app/relays/
COPY adms_control/ /app/adms_control/
COPY gis_integration/ /app/gis_integration/
COPY gis_model/ /app/gis_model/
COPY scada_model/ /app/scada_model/
COPY visualization/ /app/visualization/
COPY reporting/ /app/reporting/
COPY etap_integration/ /app/etap_integration/
COPY curves/ /app/curves/
COPY agents/ /app/agents/
COPY network_solver/ /app/network_solver/
COPY gis_validation/ /app/gis_validation/
COPY gis_validation_electrical/ /app/gis_validation_electrical/
COPY gis_validation_real/ /app/gis_validation_real/
COPY etap_user_guide/ /app/etap_user_guide/
COPY backend/ /app/backend/
COPY ml/ /app/ml/
COPY api/ /app/api/
COPY services/ /app/services/
COPY utils/ /app/utils/
COPY schemas/ /app/schemas/
COPY skills/ /app/skills/
COPY worker/ /app/worker/
COPY scripts/ /app/scripts/
COPY migrations/ /app/migrations/
COPY guards/ /app/guards/
COPY copilot/ /app/copilot/
COPY prompts/ /app/prompts/
COPY config/ /app/config/

WORKDIR /app

# Create data directories
RUN mkdir -p /data reports knowledge_db logs /app/static

# Create non-root user
RUN groupadd -r appuser &&     useradd -r -g appuser -d /app -s /sbin/nologin appuser &&     chown -R appuser:appuser /app /data

ENV PYTHONUNBUFFERED=1     PYTHONDONTWRITEBYTECODE=1     ENGINEERING_SERVICE_HOST=0.0.0.0     ENGINEERING_SERVICE_PORT=8000     LOG_LEVEL=INFO     ENVIRONMENT=production

# Security: JWT and Fernet keys MUST be provided via environment at runtime
# Do NOT hardcode secrets in the Dockerfile

EXPOSE 8000

VOLUME ["/data", "/app/reports", "/app/knowledge_db", "/app/logs"]

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3     CMD curl -fsS http://localhost:8000/health || exit 1

# Use tini as init for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

USER appuser

CMD ["python3", "engineering_service.py"]
