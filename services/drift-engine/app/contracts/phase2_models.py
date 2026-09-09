"""
Phase 2 to Phase 3 Contract Models.

Defines the interface between Phase 2 (drift simulation) and Phase 3 (AIS attribution).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Centroid(BaseModel):
    """Geographic centroid."""

    lon: float = Field(..., description="Longitude")
    lat: float = Field(..., description="Latitude")


class OriginRegion(BaseModel):
    """Estimated origin region."""

    centroid: Centroid = Field(..., description="Center of estimated origin")
    radius_km: float = Field(..., description="Search radius in kilometers")


class SearchWindow(BaseModel):
    """Spatial and temporal search window for Phase 3."""

    min_lon: float = Field(..., description="Minimum longitude")
    max_lon: float = Field(..., description="Maximum longitude")
    min_lat: float = Field(..., description="Minimum latitude")
    max_lat: float = Field(..., description="Maximum latitude")
    start_time: datetime = Field(..., description="Search window start time")
    end_time: datetime = Field(..., description="Search window end time")


class Observation(BaseModel):
    """Oil spill observation from Phase 1."""

    acquired_at: datetime = Field(..., description="Observation time")


class ForecastInfo(BaseModel):
    """Forecast information for Phase 3."""

    artifact: str = Field(..., description="Path to forecast artifact")
    forecast_hours: float = Field(..., description="Duration of forecast")


class Phase2SearchWindow(BaseModel):
    """
    Main contract: Phase 2 → Phase 3 Search Window.

    This JSON is the primary handoff from Phase 2 to Phase 3.
    """

    contract_version: str = Field(
        default="phase2-to-phase3-v1",
        description="Contract version for compatibility",
    )

    case_id: str = Field(..., description="Case identifier")
    scene_id: Optional[str] = Field(None, description="SAR scene identifier")
    generated_at: datetime = Field(..., description="When this was generated")

    # Phase 1 observation
    observation: Observation = Field(..., description="Spill observation")

    # Best result from Phase 2
    best_release_age_hours: int = Field(
        ..., description="Best-ranked candidate release age"
    )

    # Origin information
    origin: OriginRegion = Field(..., description="Estimated origin region")

    # Search window for Phase 3
    search_window: SearchWindow = Field(
        ..., description="Spatial-temporal search window for vessel search"
    )

    # Forecast
    forecast: Optional[ForecastInfo] = Field(
        None, description="Forecast information"
    )

    # Artifact references
    artifacts: list[str] = Field(
        default_factory=list, description="List of output artifact paths"
    )

    # Metadata
    random_seed: Optional[int] = Field(
        None, description="Random seed used for reproducibility"
    )
    phase2_run_id: Optional[str] = Field(None, description="Phase 2 run identifier")


class Phase2ArtifactManifest(BaseModel):
    """Manifest of all Phase 2 output artifacts."""

    contract_version: str = Field(
        default="phase2-artifact-manifest-v1",
        description="Manifest contract version",
    )
    run_id: str = Field(..., description="Phase 2 run ID")
    case_id: str = Field(..., description="Case ID")
    status: str = Field(..., description="Run status (SUCCESS, FAILED, etc.)")
    created_at: datetime = Field(..., description="Artifact creation time")

    artifacts: list[dict] = Field(
        default_factory=list,
        description="List of artifacts with type, path, format, size, etc.",
    )