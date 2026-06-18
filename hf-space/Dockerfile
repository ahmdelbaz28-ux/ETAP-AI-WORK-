FROM python:3.11-slim

LABEL maintainer="Eng. Ahmed Elbaz <ahmdelbaz28@gmail.com>"
LABEL description="AhmedETAP — Enterprise Engineering Intelligence Platform"
LABEL version="2.1.0"

WORKDIR /app

# ─── System dependencies ──────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

# ─── Python dependencies ──────────────────────────────────────────────────────
COPY requirements.hf.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.hf.txt

# ─── Application code ─────────────────────────────────────────────────────────
COPY . .

# ─── Writable dirs for HF Spaces (only /tmp is writable) ─────────────────────
RUN mkdir -p /tmp/cache /tmp/logs /tmp/data && chmod -R 777 /tmp

# ─── Environment ──────────────────────────────────────────────────────────────
ENV PORT=7860
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV MPLCONFIGDIR=/tmp/cache
ENV XDG_CACHE_HOME=/tmp/cache
ENV HF_HOME=/tmp/cache

# ─── Health check ─────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:7860/healthz || exit 1

EXPOSE 7860

CMD ["python", "app.py"]
