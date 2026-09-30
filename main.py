"""Extraction service FastAPI application: bootstrap y montaje de componentes."""

from fastapi import FastAPI
from shared.web.cors import add_cors
from shared.web.logging import RequestIdMiddleware, setup_logging

from routes import router

SERVICE_NAME = "extraction-service"

setup_logging(SERVICE_NAME)

app = FastAPI(title="PDF Extraction Service", version="1.0.0")

app.add_middleware(RequestIdMiddleware)
add_cors(app)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": SERVICE_NAME}


app.include_router(router)