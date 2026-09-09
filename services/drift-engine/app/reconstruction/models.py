"""Reconstruction result models."""

from typing import Optional

from pydantic import BaseModel, Field

from app.simulation.models import SimulationResult


class ReconstructionMetrics(BaseModel):
    """Metrics for reconstruction quality."""

    centroid_distance_km: float = Field(
        ..., description="Distance from reconstructed to observed centroid (km)"
    )
    overlap_score: float = Field(
        ..., ge=0, le=1, description="Spatial overlap with observed polygon (0-1)"
    )
    particle_coverage: float = Field(
        ..., ge=0, le=1, description="Fraction of particles within observation region"
    )
    overall_score: float = Field(
        ..., ge=0, le=1, description="Overall reconstruction quality (0-1)"
    )


class ReconstructionResult(BaseModel):
    """Result of forward reconstruction."""

    run_id: str = Field(..., description="Phase 2 run ID")
    simulation_result: SimulationResult = Field(..., description="Simulation output")
    metrics: ReconstructionMetrics = Field(..., description="Quality metrics")

    class Config:
        """Config."""

        arbitrary_types_allowed = True