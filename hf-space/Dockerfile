FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.hf.txt .
RUN pip install --no-cache-dir -r requirements.hf.txt

COPY . .

RUN mkdir -p /tmp/cache /tmp/logs /tmp/data && chmod -R 777 /tmp

ENV PORT=7860
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

EXPOSE 7860

CMD ["python", "app.py"]
