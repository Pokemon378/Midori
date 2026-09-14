"""Midori — Crop Health Intelligence Platform backend entrypoint.

Step 1: FastAPI foundation only. Later modules (database, feature engine,
risk engine, AI vision, camera workflow) will be added under this app package.
"""

from fastapi import FastAPI
from pydantic import BaseModel

from app.api import crops, farms, features, sensor_readings, zones
from app.database import Base, engine
from app.models import (  # noqa: F401  (register models)
    crop,
    farm,
    sensor_reading,
    zone,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Midori Crop Health Intelligence Platform",
    description=(
        "Software-based crop health monitoring, early risk detection "
        "and decision support platform."
    ),
    version="0.1.0",
)

app.include_router(farms.router)
app.include_router(zones.router)
app.include_router(crops.router)
app.include_router(sensor_readings.router)
app.include_router(features.router)


class RootResponse(BaseModel):
    """Response schema for the root endpoint."""

    message: str


class HealthResponse(BaseModel):
    """Response schema for the health endpoint."""

    status: str


@app.get("/", response_model=RootResponse)
def root() -> RootResponse:
    """Confirm that the Midori backend is running."""
    return RootResponse(message="Midori backend is running")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Health check used to verify the backend is reachable."""
    return HealthResponse(status="ok")
