"""Hindcast models for backward ensemble."""

from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field

from app.simulation.models import SimulationResult


class HindcastReleaseAge(BaseModel):
    """Configuration for one release age candidate."""

    release_age_hours: int = Field(..., description="Hours before observation")
    simulation_result: Optional[SimulationResult] = Field(
        None, description="Completed simulation"
    )
    ranking_score: Optional[float] = Field(
        None, description="Reconstruction score (0-1)"
    )
    rank: Optional[int] = Field(None, description="Ranking position")

    class Config:
        """Config."""

        arbitrary_types_allowed = True


class HindcastResult(BaseModel):
    """Result of backward ensemble simulation."""

    run_id: str = Field(..., description="Phase 2 run ID")
    observation_time: datetime = Field(..., description="Observed spill time")

    release_ages: list[HindcastReleaseAge] = Field(
        ..., description="Results for each release age candidate"
    )

    class Config:
        """Config."""

        arbitrary_types_allowed = True

    @property
    def best_release_age(self) -> Optional[HindcastReleaseAge]:
        """Get the best-ranked release age."""
        ranked = [ra for ra in self.release_ages if ra.rank is not None]
        if not ranked:
            return None
        return min(ranked, key=lambda x: x.rank)

    @property
    def ranked_ages(self) -> list[HindcastReleaseAge]:
        """Get release ages sorted by rank."""
        return sorted(
            [ra for ra in self.release_ages if ra.rank is not None],
            key=lambda x: x.rank,
        )