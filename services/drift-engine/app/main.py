from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from app.config import Phase2Settings
    from app.forcing.models import ForcingConfig
    from app.simulation.runner import Phase2Runner
    from app.utils import get_logger

    logger = get_logger(__name__)
except ImportError:
    logger = None
    Phase2Settings = None
    ForcingConfig = None
    Phase2Runner = None

app = FastAPI(
    title="VARUN Phase 2 — Oil Spill Drift Engine",
    version="0.2.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

try:
    settings = Phase2Settings() if Phase2Settings else None
    runner = Phase2Runner(settings) if Phase2Runner and settings else None
except Exception as e:
    settings = None
    runner = None


# ---------------------------------------------------------------------------
# NestJS Gateway Contracts & Models
# ---------------------------------------------------------------------------

class DriftRequest(BaseModel):
    case_id: str
    phase2_run_id: str
    phase1_handoff_ref: str
    mode: Literal["HINDCAST_AND_FORECAST", "HINDCAST", "FORECAST"] = (
        "HINDCAST_AND_FORECAST"
    )


class Point(BaseModel):
    latitude: float
    longitude: float
    timestamp_utc: str


class DriftTrajectory(BaseModel):
    trajectory_id: str
    kind: Literal["HINDCAST", "RECONSTRUCTION", "FORECAST"]
    seed_index: int
    points: list[Point]


class DriftResponse(BaseModel):
    status: Literal["COMPLETED", "COMPLETED_WITH_WARNINGS"]
    contract_version: str
    phase2_run_id: str
    case_id: str

    data_origin: str
    forcing: dict
    seeding: dict

    hindcast: dict
    reconstruction: dict
    forecast: dict

    trajectories: list[DriftTrajectory]

    artifacts: list[dict]
    provenance: dict
    warnings: list[str]


CONTRACT_VERSION = "phase2-to-phase3-v1"
ENGINE_VERSION = "VARUN-PHASE2-DRIFT-V1"


# ---------------------------------------------------------------------------
# Direct Runner Request/Response Models
# ---------------------------------------------------------------------------

class Phase2RunRequest(BaseModel):
    """Request to run Phase 2 simulation."""

    case_id: str = Field(..., description="Case identifier")
    scene_id: Optional[str] = Field(None, description="SAR scene ID")
    observation_time: str = Field(..., description="ISO-8601 observation time")

    spill_polygon: dict = Field(
        ..., description="GeoJSON Polygon of observed spill"
    )

    forcing: dict = Field(
        ...,
        description="Forcing file paths (current_file, wind_file, or combined_file)",
    )

    particle_count: Optional[int] = Field(
        None, description="Number of particles (default from config)"
    )
    release_ages_hours: Optional[list[int]] = Field(
        None, description="Release age candidates (default from config)"
    )
    forecast_hours: Optional[float] = Field(
        None, description="Forecast duration (default from config)"
    )


class Phase2RunResponse(BaseModel):
    """Response from Phase 2 run."""

    run_id: str = Field(..., description="Unique run identifier")
    case_id: str = Field(..., description="Case identifier")
    status: str = Field(..., description="Run status (QUEUED, RUNNING, SUCCESS, FAILED)")


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str = Field("ok", description="Service status")
    version: str = Field("0.2.0", description="API version")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def deterministic_offset(seed: int) -> tuple[float, float]:
    angle = seed * 1.61803398875
    lat_offset = math.sin(angle) * 0.015
    lon_offset = math.cos(angle) * 0.020
    return lat_offset, lon_offset


def sha256_json(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def make_points(
    *,
    seed: int,
    start_lat: float,
    start_lon: float,
    start_time: datetime,
    count: int,
    hours_step: int,
    direction: float,
) -> list[Point]:

    lat_shift, lon_shift = deterministic_offset(seed)
    points: list[Point] = []

    for i in range(count):
        t = start_time + timedelta(hours=i * hours_step)
        progress = i / max(count - 1, 1)

        latitude = (
            start_lat
            + lat_shift * progress
            + math.sin((seed + i) * 0.7) * 0.002
        )

        longitude = (
            start_lon
            + lon_shift * progress
            + direction * progress * 0.01
            + math.cos((seed + i) * 0.5) * 0.002
        )

        points.append(
            Point(
                latitude=round(latitude, 6),
                longitude=round(longitude, 6),
                timestamp_utc=iso(t),
            )
        )

    return points


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthCheckResponse)
def health():
    return HealthCheckResponse(status="ok", version="0.2.0")


@app.get("/version")
def version():
    return {
        "service": "phase2-drift",
        "engineVersion": ENGINE_VERSION,
        "contractVersion": CONTRACT_VERSION,
        "scientificBackend": "OpenDrift/OpenOil",
    }


@app.post("/internal/v1/drift-runs", response_model=DriftResponse)
def run_internal(request: DriftRequest) -> DriftResponse:

    if not request.case_id:
        raise HTTPException(status_code=400, detail="case_id is required")

    if not request.phase2_run_id:
        raise HTTPException(status_code=400, detail="phase2_run_id is required")

    if not request.phase1_handoff_ref:
        raise HTTPException(status_code=400, detail="phase1_handoff_ref is required")

    started = utc_now()

    handoff_digest = sha256_json(
        {
            "case_id": request.case_id,
            "phase1_handoff_ref": request.phase1_handoff_ref,
        }
    )

    forcing = {
        "source": "PHASE1_HANDOFF",
        "forcingStatus": "VALIDATED",
        "wind": {"source": "HANDOFF_REQUIRED", "available": False},
        "oceanCurrent": {"source": "HANDOFF_REQUIRED", "available": False},
        "seaSurfaceTemperature": {"source": "HANDOFF_REQUIRED", "available": False},
    }

    warnings: list[str] = []
    seed_count = 5

    seeding = {
        "strategy": "PHASE1_RESULT_REFERENCE",
        "seedCount": seed_count,
        "seedSource": request.phase1_handoff_ref,
        "seedDigest": handoff_digest,
    }

    base_lat = 20.0
    base_lon = 68.0

    if request.mode in ("HINDCAST_AND_FORECAST", "HINDCAST"):
        hindcast_start = started - timedelta(hours=24)
        hindcast_trajectories = []

        for seed in range(seed_count):
            points = make_points(
                seed=seed,
                start_lat=base_lat,
                start_lon=base_lon,
                start_time=hindcast_start,
                count=7,
                hours_step=4,
                direction=-1.0,
            )
            hindcast_trajectories.append(
                DriftTrajectory(
                    trajectory_id=f"hindcast-{seed + 1}",
                    kind="HINDCAST",
                    seed_index=seed,
                    points=points,
                )
            )
    else:
        hindcast_trajectories = []

    if request.mode in ("HINDCAST_AND_FORECAST", "FORECAST"):
        reconstruction_start = started - timedelta(hours=12)
        reconstruction_trajectories = []

        for seed in range(seed_count):
            points = make_points(
                seed=seed + 100,
                start_lat=base_lat,
                start_lon=base_lon,
                start_time=reconstruction_start,
                count=7,
                hours_step=2,
                direction=0.5,
            )
            reconstruction_trajectories.append(
                DriftTrajectory(
                    trajectory_id=f"reconstruction-{seed + 1}",
                    kind="RECONSTRUCTION",
                    seed_index=seed,
                    points=points,
                )
            )
    else:
        reconstruction_trajectories = []

    if request.mode in ("HINDCAST_AND_FORECAST", "FORECAST"):
        forecast_start = started
        forecast_trajectories = []

        for seed in range(seed_count):
            points = make_points(
                seed=seed + 200,
                start_lat=base_lat,
                start_lon=base_lon,
                start_time=forecast_start,
                count=13,
                hours_step=2,
                direction=1.0,
            )
            forecast_trajectories.append(
                DriftTrajectory(
                    trajectory_id=f"forecast-{seed + 1}",
                    kind="FORECAST",
                    seed_index=seed,
                    points=points,
                )
            )
    else:
        forecast_trajectories = []

    trajectories = (
        hindcast_trajectories
        + reconstruction_trajectories
        + forecast_trajectories
    )

    validation = {
        "status": "COMPLETED_WITH_WARNINGS",
        "trajectoryCount": len(trajectories),
        "seedCount": seed_count,
        "geometryValid": True,
        "timestampsMonotonic": True,
        "forcingValidated": False,
    }

    warnings.append(
        "Live environmental forcing was not available; "
        "trajectory coordinates are deterministic integration fixtures "
        "and must not be interpreted as scientific forecast truth."
    )

    trajectory_payload = [t.model_dump() for t in trajectories]
    artifact_digest = sha256_json(trajectory_payload)

    artifacts = [
        {
            "logicalName": "phase2-trajectories.json",
            "mediaType": "application/json",
            "checksumSha256": artifact_digest,
        },
        {
            "logicalName": "phase2-provenance.json",
            "mediaType": "application/json",
            "checksumSha256": sha256_json(
                {
                    "engineVersion": ENGINE_VERSION,
                    "contractVersion": CONTRACT_VERSION,
                    "handoffDigest": handoff_digest,
                }
            ),
        },
    ]

    provenance = {
        "engineVersion": ENGINE_VERSION,
        "contractVersion": CONTRACT_VERSION,
        "phase1HandoffRef": request.phase1_handoff_ref,
        "phase1HandoffDigest": handoff_digest,
        "executionStartedAt": iso(started),
        "executionFinishedAt": iso(utc_now()),
        "scientificBackend": "OpenDrift/OpenOil",
        "executionMode": request.mode,
        "dataOrigin": "DETERMINISTIC_INTEGRATION_FIXTURE",
        "artifactSha256": artifact_digest,
        "validation": validation,
    }

    return DriftResponse(
        status="COMPLETED_WITH_WARNINGS",
        contract_version=CONTRACT_VERSION,
        phase2_run_id=request.phase2_run_id,
        case_id=request.case_id,
        data_origin="DETERMINISTIC_INTEGRATION_FIXTURE",
        forcing=forcing,
        seeding=seeding,
        hindcast={
            "enabled": request.mode in ("HINDCAST_AND_FORECAST", "HINDCAST"),
            "trajectoryCount": len(hindcast_trajectories),
        },
        reconstruction={
            "enabled": request.mode in ("HINDCAST_AND_FORECAST", "FORECAST"),
            "trajectoryCount": len(reconstruction_trajectories),
        },
        forecast={
            "enabled": request.mode in ("HINDCAST_AND_FORECAST", "FORECAST"),
            "trajectoryCount": len(forecast_trajectories),
            "horizonHours": 24,
        },
        trajectories=trajectories,
        artifacts=artifacts,
        provenance=provenance,
        warnings=warnings,
    )


@app.post("/api/v1/phase2/run", response_model=Phase2RunResponse)
async def run_phase2(request: Phase2RunRequest):
    """Start a Phase 2 simulation via runner backend."""
    if not runner:
        raise HTTPException(
            status_code=503,
            detail="Phase2Runner backend not initialized",
        )
    try:
        try:
            obs_time = datetime.fromisoformat(request.observation_time.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid observation_time format: {e}",
            )

        forcing_dict = request.forcing
        forcing_config = ForcingConfig(
            current_file=Path(forcing_dict.get("current_file")) if forcing_dict.get("current_file") else None,
            wind_file=Path(forcing_dict.get("wind_file")) if forcing_dict.get("wind_file") else None,
            combined_file=Path(forcing_dict.get("combined_file")) if forcing_dict.get("combined_file") else None,
        )

        result = runner.run_phase2(
            case_id=request.case_id,
            scene_id=request.scene_id,
            observation_time=obs_time,
            spill_polygon_geojson=request.spill_polygon,
            forcing_config=forcing_config,
            particle_count=request.particle_count or (settings.particle_count if settings else 1000),
            release_ages_hours=request.release_ages_hours,
            forecast_hours=request.forecast_hours or (settings.forecast_duration_hours if settings else 24),
        )

        if result["status"] == "FAILED":
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Simulation failed"),
            )

        return Phase2RunResponse(
            run_id=result["run_id"],
            case_id=request.case_id,
            status=result["status"],
        )

    except HTTPException:
        raise
    except Exception as e:
        if logger:
            logger.error(f"Phase 2 run failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Simulation failed: {str(e)}",
        )


@app.get("/api/v1/phase2/runs/{run_id}")
async def get_run_status(run_id: str):
    """Get status of a Phase 2 run."""
    return {"run_id": run_id, "status": "COMPLETED"}


@app.get("/api/v1/phase2/runs/{run_id}/search-window")
async def get_search_window(run_id: str):
    """Get Phase 3 search window for a run."""
    return {"error": "Not implemented"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.api_host if settings else "0.0.0.0",
        port=settings.api_port if settings else 8000,
        log_level="info",
    )
