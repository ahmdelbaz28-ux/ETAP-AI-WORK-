# services/yolo/Dockerfile — YOLO Layout Segmentation Service for AhmedETAP
FROM python:3.13-slim

WORKDIR /app

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgl1-mesa-glx \
    libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip==25.1.1 && \
    pip install --no-cache-dir --only-binary :all: -r requirements.txt

COPY main.py ./
# Create non-root user for security (S6471)
RUN useradd -m -u 1000 appuser
USER 1000

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
