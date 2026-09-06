
from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.inference import router as inference_router

app = FastAPI(
    title="VARUN Detection Engine",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(inference_router, prefix="/v1")


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "detection-engine",
        "version": "0.1.0",
    }