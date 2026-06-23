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

# Application code
COPY --chown=user:user . .

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

# Database path (use /tmp for writable location)
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
