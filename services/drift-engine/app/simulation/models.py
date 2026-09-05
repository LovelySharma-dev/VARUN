"""
Simulation models for Phase 2.

Represents simulation configuration and results.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field


class SimulationDirection(str, Enum):
    """Direction of simulation."""

    FORWARD = "forward"
    BACKWARD = "backward"


class SimulationStatus(str, Enum):
    """Status of a simulation."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SimulationConfig(BaseModel):
    """Configuration for a single simulation."""

    direction: SimulationDirection = Field(
        ..., description="Forward or backward simulation"
    )
    start_time: datetime = Field(..., description="Simulation start time")
    end_time: datetime = Field(..., description="Simulation end time")
    initial_lats: list[float] = Field(..., description="Initial particle latitudes")
    initial_lons: list[float] = Field(..., description="Initial particle longitudes")
    time_step_hours: float = Field(
        default=1.0, description="Integration time step (hours)"
    )
    output_interval_hours: float = Field(
        default=1.0, description="Output storage interval (hours)"
    )

    class Config:
        """Pydantic config."""

        frozen = False


class SimulationResult(BaseModel):
    """Result of a completed simulation."""

    simulation_id: str = Field(..., description="Unique simulation ID")
    config: SimulationConfig = Field(..., description="Simulation configuration")
    status: SimulationStatus = Field(
        default=SimulationStatus.COMPLETED, description="Simulation status"
    )
    start_time: datetime = Field(..., description="Actual start time")
    end_time: datetime = Field(..., description="Actual end time")

    # Trajectory data
    trajectory_times: list[datetime] = Field(
        ..., description="Time points in trajectory"
    )
    trajectory_lats: np.ndarray = Field(
        ..., description="Latitude trajectory (n_times, n_particles)"
    )
    trajectory_lons: np.ndarray = Field(
        ..., description="Longitude trajectory (n_times, n_particles)"
    )

    # Optional status data
    particle_status: Optional[np.ndarray] = Field(
        default=None, description="Particle status codes at final time"
    )

    output_file: Optional[Path] = Field(
        default=None, description="Path to output NetCDF file"
    )

    class Config:
        """Allow numpy arrays."""

        arbitrary_types_allowed = True

    @property
    def particle_count(self) -> int:
        """Number of particles in simulation."""
        return self.trajectory_lats.shape[1]

    @property
    def time_steps(self) -> int:
        """Number of time steps in output."""
        return len(self.trajectory_times)

    @property
    def duration_hours(self) -> float:
        """Simulation duration in hours."""
        return (self.end_time - self.start_time).total_seconds() / 3600

    def get_final_positions(self) -> tuple[np.ndarray, np.ndarray]:
        """Get final particle positions."""
        return self.trajectory_lats[-1], self.trajectory_lons[-1]

    def get_positions_at_time_index(self, idx: int) -> tuple[np.ndarray, np.ndarray]:
        """Get particle positions at specific time index."""
        return self.trajectory_lats[idx], self.trajectory_lons[idx]