# =============================================================================
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
LABEL version="1.1.0"

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
COPY main.py /app/
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