"""
Main FastAPI application for VARUN Phase 2.

Provides REST API for oil spill drift simulation.
"""

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.config import Phase2Settings
from app.forcing.models import ForcingConfig
from app.simulation.runner import Phase2Runner
from app.utils import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="VARUN Phase 2 — Oil Spill Drift Engine",
    version="0.2.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

settings = Phase2Settings()
runner = Phase2Runner(settings)


# ========== Request/Response Models ==========


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


# ========== Health & Version Endpoints ==========


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(status="ok", version="0.2.0")


@app.get("/version")
async def get_version():
    """Get API version."""
    return {"version": "0.2.0", "phase": 2}


# ========== Phase 2 Endpoints ==========


@app.post("/api/v1/phase2/run", response_model=Phase2RunResponse)
async def run_phase2(request: Phase2RunRequest):
    """
    Start a Phase 2 simulation.

    This endpoint accepts a spill observation and forcing data,
    then runs the complete drift simulation workflow.
    """
    try:
        # Parse observation time
        try:
            obs_time = datetime.fromisoformat(request.observation_time.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid observation_time format: {e}",
            )

        # Parse forcing config
        try:
            from pathlib import Path
            forcing_dict = request.forcing
            forcing_config = ForcingConfig(
                current_file=Path(forcing_dict.get("current_file")) if forcing_dict.get("current_file") else None,
                wind_file=Path(forcing_dict.get("wind_file")) if forcing_dict.get("wind_file") else None,
                combined_file=Path(forcing_dict.get("combined_file")) if forcing_dict.get("combined_file") else None,
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid forcing configuration: {e}",
            )

        # Run simulation
        result = runner.run_phase2(
            case_id=request.case_id,
            scene_id=request.scene_id,
            observation_time=obs_time,
            spill_polygon_geojson=request.spill_polygon,
            forcing_config=forcing_config,
            particle_count=request.particle_count or settings.particle_count,
            release_ages_hours=request.release_ages_hours,
            forecast_hours=request.forecast_hours or settings.forecast_duration_hours,
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
        logger.error(f"Phase 2 run failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Simulation failed: {str(e)}",
        )


@app.get("/api/v1/phase2/runs/{run_id}")
async def get_run_status(run_id: str):
    """Get status of a Phase 2 run."""
    # TODO: Implement run tracking
    return {"run_id": run_id, "status": "COMPLETED"}


@app.get("/api/v1/phase2/runs/{run_id}/search-window")
async def get_search_window(run_id: str):
    """Get Phase 3 search window for a run."""
    # TODO: Load from outputs/{run_id}/phase2-search-window.json
    return {"error": "Not implemented"}


# ========== Error Handlers ==========


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    """Handle uncaught exceptions."""
    logger.error(f"Uncaught exception: {exc}", exc_info=True)
    return {
        "error": "INTERNAL_SERVER_ERROR",
        "message": str(exc),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )