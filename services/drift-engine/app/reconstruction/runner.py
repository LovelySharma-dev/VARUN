"""Forward reconstruction runner."""

import logging
from datetime import timedelta
from typing import Optional

import numpy as np

from app.reconstruction.models import ReconstructionMetrics, ReconstructionResult
from app.seeding.models import SeedingConfig
from app.seeding.polygon import seed_from_point
from app.simulation.engine import DriftSimulationEngine
from app.simulation.models import SimulationConfig, SimulationDirection
from app.utils import haversine_distance, normalize_simulation_time

logger = logging.getLogger(__name__)


def run_reconstruction(
    run_id: str,
    best_origin_lat: float,
    best_origin_lon: float,
    observation_time,
    release_age_hours: int,
    readers: list,
    engine: DriftSimulationEngine,
    seeding_config: SeedingConfig,
    radius_km: float = 5.0,
) -> Optional[ReconstructionResult]:
    """
    Run fresh forward simulation from estimated origin.

    Args:
        run_id: Phase 2 run ID
        best_origin_lat: Latitude of estimated origin
        best_origin_lon: Longitude of estimated origin
        observation_time: Time of observation
        release_age_hours: Best release age in hours
        readers: OpenDrift readers
        engine: Simulation engine
        seeding_config: Seeding configuration
        radius_km: Radius around origin for seeding

    Returns:
        ReconstructionResult with metrics
    """
    logger.info(f"Running forward reconstruction from estimated origin")
    logger.info(f"  Origin: ({best_origin_lat:.3f}, {best_origin_lon:.3f})")
    logger.info(f"  Release age: {release_age_hours}h")

    observation_time_norm = normalize_simulation_time(
        observation_time, "observation_time"
    )

    release_time = observation_time_norm - timedelta(hours=release_age_hours)

    # Seed from origin point
    seeding_result = seed_from_point(
        best_origin_lat,
        best_origin_lon,
        radius_km,
        release_time,
        seeding_config,
    )

    logger.info(f"Seeded {seeding_result.effective_particle_count} particles at origin")

    # Run forward simulation
    sim_config = SimulationConfig(
        direction=SimulationDirection.FORWARD,
        start_time=release_time,
        end_time=observation_time_norm,
        initial_lats=seeding_result.get_initial_lats().tolist(),
        initial_lons=seeding_result.get_initial_lons().tolist(),
    )

    try:
        sim_id = f"{run_id}-RECONSTRUCTION"
        sim_result = engine.run_simulation(sim_config, readers, sim_id)
        logger.info("Forward reconstruction simulation completed")
    except Exception as e:
        logger.error(f"Reconstruction simulation failed: {e}")
        return None

    # Calculate metrics
    final_lats, final_lons = sim_result.get_final_positions()

    # Placeholder metrics - would be extended
    metrics = ReconstructionMetrics(
        centroid_distance_km=0.0,
        overlap_score=0.0,
        particle_coverage=0.0,
        overall_score=0.0,
    )

    result = ReconstructionResult(
        run_id=run_id,
        simulation_result=sim_result,
        metrics=metrics,
    )

    return result


class ReconstructionRunner:
    """Runner for forward reconstruction."""

    def __init__(self, engine: DriftSimulationEngine):
        """Initialize with simulation engine."""
        self.engine = engine

    def run(
        self,
        run_id: str,
        best_origin_lat: float,
        best_origin_lon: float,
        observation_time,
        release_age_hours: int,
        readers: list,
        seeding_config: SeedingConfig,
    ) -> Optional[ReconstructionResult]:
        """Run reconstruction."""
        return run_reconstruction(
            run_id,
            best_origin_lat,
            best_origin_lon,
            observation_time,
            release_age_hours,
            readers,
            self.engine,
            seeding_config,
        )