# =============================================================================
# ETAP AI Engineering Platform - Multi-Stage Docker Build
# =============================================================================
# Stage 1: Python Builder
FROM python:3.14-slim AS python-builder

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

RUN pnpm install --frozen-lockfile

COPY . .

RUN pnpm build

# Remove dev dependencies to reduce size
RUN pnpm prune --prod

# =============================================================================
# Stage 3: Runtime
FROM node:20-slim

LABEL maintainer="ETAP AI Platform Team"
LABEL description="AI-powered ETAP Engineering Platform - Multi-Arch"
LABEL version="1.1.0"

# Install Python runtime only (no build tools)
RUN apt-get update && apt-get install -y     python3     python3-pip     python3-venv     curl     tini     --no-install-recommends     && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=python-builder /install /usr/local

# Copy Node.js application from builder
COPY --from=ts-builder /build /app

WORKDIR /app

# Create data directories
RUN mkdir -p /data reports knowledge_db logs /app/static

# Create non-root user
RUN groupadd -r appuser &&     useradd -r -g appuser -d /app -s /sbin/nologin appuser &&     chown -R appuser:appuser /app /data

ENV PYTHONUNBUFFERED=1     PYTHONDONTWRITEBYTECODE=1     APP_HOST=0.0.0.0     APP_PORT=3000     LOG_LEVEL=INFO     NODE_ENV=production

EXPOSE 3000

VOLUME ["/data", "/app/reports", "/app/knowledge_db", "/app/logs"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3     CMD curl -f http://localhost:3000/health || curl -f http://localhost:3000/api/health || exit 1

# Use tini as init for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

USER appuser

CMD ["node", "/app/dist/index.js"]
