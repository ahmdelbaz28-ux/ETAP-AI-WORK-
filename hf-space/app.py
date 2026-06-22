"""AhmedETAP - HF Spaces Entry Point"""

import os
import time
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="AhmedETAP", version="1.0.0")
START_TIME = time.time()


@app.get("/")
async def root():
    return {"name": "AhmedETAP", "version": "1.0.0", "status": "running", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy", "uptime": round(time.time() - START_TIME, 2)}


@app.get("/healthz")
async def healthz():
    return JSONResponse(content="OK", status_code=200)


@app.get("/readyz")
async def readyz():
    return JSONResponse(content="OK", status_code=200)


@app.get("/ready")
async def ready():
    return {"status": "ready"}


@app.get("/metrics")
async def metrics():
    return {"uptime_seconds": round(time.time() - START_TIME, 2)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)))
