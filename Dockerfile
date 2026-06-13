# =============================================================================
# ETAP AI Engineering Platform - Multi-Stage Docker Build
# =============================================================================
# Stage 1: Python Builder
FROM python:3.13-slim AS python-builder

LABEL stage="python-builder"

RUN apt-get update && apt-get install -y     gcc     g++     curl     --no-install-recommends     && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip &&     pip install --no-cache-dir         --prefix=/install         $(grep -v "pywin32" requirements.txt | grep -v "^#" | grep -v "^$" | tr '\n' ' ')

# =============================================================================
# Stage 2: TypeScript / Node Builder
FROM node:20-slim AS ts-builder

LABEL stage="ts-builder"

RUN apt-get update && apt-get install -y     curl     --no-install-recommends     && rm -rf /var/lib/apt/lists/*

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /build

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

RUN pnpm install --no-frozen-lockfile

COPY . .

RUN pnpm build

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

# Copy application source
COPY --from=ts-builder /build/.next /app/.next
COPY --from=ts-builder /build/node_modules /app/node_modules
COPY --from=ts-builder /build/package.json /app/package.json
COPY --from=ts-builder /build/public /app/public
COPY --from=ts-builder /build/src /app/src

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

WORKDIR /app

# Create data directories
RUN mkdir -p /data reports knowledge_db logs /app/static

# Create non-root user
RUN groupadd -r appuser &&     useradd -r -g appuser -d /app -s /sbin/nologin appuser &&     chown -R appuser:appuser /app /data

ENV PYTHONUNBUFFERED=1     PYTHONDONTWRITEBYTECODE=1     ENGINEERING_SERVICE_HOST=0.0.0.0     ENGINEERING_SERVICE_PORT=8000     LOG_LEVEL=INFO

EXPOSE 8000

VOLUME ["/data", "/app/reports", "/app/knowledge_db", "/app/logs"]

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3     CMD curl -fsS http://localhost:8000/health || exit 1

# Use tini as init for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

USER appuser

CMD ["python3", "engineering_service.py"]
