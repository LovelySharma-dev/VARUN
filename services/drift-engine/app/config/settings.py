"""
Configuration for VARUN Phase 2 Drift Engine.

All scientific and operational parameters are configured here.
Use environment variables or YAML config files to override.
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Phase2Settings(BaseSettings):
    """Phase 2 configuration settings."""

    # == Project paths ==
    project_root: Path = Path(__file__).parent.parent.parent
    data_dir: Path = project_root / "data"
    forcing_dir: Path = data_dir / "forcing"
    output_dir: Path = project_root / "outputs"

    # == Particle seeding ==
    particle_count: int = 1500
    """Number of particles for forward/backward simulations"""

    seed_buffer_km: float = 2.0
    """Buffer around spill polygon for particle seeding (km)"""

    # == Release ages (hours before observation) ==
    release_ages_hours: list[int] = [6, 12, 24, 36]
    """Candidate release ages to simulate (hours before observation)"""

    # == Simulation parameters ==
    simulation_time_step_hours: float = 0.25
    """Integration time step (hours)"""

    output_interval_hours: float = 0.5
    """Output interval for trajectory storage (hours)"""

    forecast_duration_hours: float = 24.0
    """Forward forecast duration from observation time (hours)"""

    # == Uncertainty parameters ==
    current_uncertainty_fraction: float = 0.1
    """Relative uncertainty in current velocity (fraction)"""

    wind_uncertainty_fraction: float = 0.15
    """Relative uncertainty in wind velocity (fraction)"""

    # == Density and contours ==
    density_grid_resolution_km: float = 1.0
    """Resolution of origin density grid (km)"""

    contour_levels: list[float] = [0.50, 0.75, 0.90]
    """Contour probability levels for origin density"""

    # == Reproducibility ==
    random_seed: Optional[int] = 42
    """Random seed for reproducible particle seeding. None for random."""

    # == Feature flags ==
    validate_polygon_intersection: bool = True
    """Validate that spill polygon intersects forcing domain"""

    validate_no_particles_on_land: bool = True
    """Warn if many particles are removed due to land masking"""

    land_particle_warning_threshold: float = 0.25
    """Warn if >25% of particles are on land"""

    # == Release age ranking ==
    ranking_method: str = "reconstruction_overlap"
    """Method for ranking release ages: 'reconstruction_overlap', 'particle_distance', etc."""

    # == API ==
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = False

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Phase2Settings()