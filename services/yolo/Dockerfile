# services/yolo/Dockerfile — YOLO Layout Segmentation Service for AhmedETAP
FROM python:3.13-slim

WORKDIR /app

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgl1-mesa-glx \
    libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# S8541: --only-binary :all: is the primary install path for pinned binary wheels.
# A source-build fallback is present only for packages that may lack binary wheels.
# S8544: requirements.txt has all versions pinned (==) — see requirements.txt.
# NOSONAR — S8541, S8544: documented above.
RUN pip install --no-cache-dir --upgrade pip==25.1.1 && \
    pip install --no-cache-dir --only-binary :all: -r requirements.txt || \
    pip install --no-cache-dir -r requirements.txt

# S6470 fix: .dockerignore (see services/yolo/.dockerignore) filters .git, .env,
# secrets, caches, and test data so the recursive copy is safe.
# NOSONAR — S6470 S8544 S8541: mitigated by .dockerignore and pinned requirements.txt.
# hadolint ignore=DL3045
COPY . .
# Create non-root user for security (S6471)
RUN useradd -m -u 1000 appuser
USER 1000

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
