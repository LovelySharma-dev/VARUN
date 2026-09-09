"""
Particle seeding models for Phase 2.

Represents particle seed configurations and results.
"""

from datetime import datetime
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field


class SeedingConfig(BaseModel):
    """Configuration for particle seeding."""

    particle_count: int = Field(
        ..., gt=0, description="Number of particles to seed"
    )
    seed_buffer_km: float = Field(
        ..., ge=0, description="Buffer around polygon for seeding (km)"
    )
    random_seed: Optional[int] = Field(
        None, description="Random seed for reproducibility"
    )

    class Config:
        """Pydantic config."""

        frozen = False


class SeedingResult(BaseModel):
    """Result of particle seeding operation."""

    particle_count: int = Field(..., description="Number of particles seeded")
    initial_positions: dict = Field(
        ..., description="Initial lat/lon positions (numpy arrays as dicts)"
    )
    seeding_time: datetime = Field(..., description="Time at which particles were seeded")
    seed_geom_wkt: Optional[str] = Field(None, description="Seed geometry as WKT")
    particles_on_land_count: int = Field(
        default=0, description="Number of particles removed due to land masking"
    )
    effective_particle_count: int = Field(
        ..., description="Actual number of particles after land removal"
    )

    class Config:
        """Allow numpy arrays via dict serialization."""

        arbitrary_types_allowed = True

    def get_initial_lats(self) -> np.ndarray:
        """Get initial latitudes."""
        return np.array(self.initial_positions["lats"])

    def get_initial_lons(self) -> np.ndarray:
        """Get initial longitudes."""
        return np.array(self.initial_positions["lons"])

    def summary(self) -> dict:
        """Get summary of seeding result."""
        return {
            "particle_count": self.particle_count,
            "effective_particle_count": self.effective_particle_count,
            "particles_on_land_count": self.particles_on_land_count,
            "seeding_time": self.seeding_time.isoformat(),
        }