"""Hindcast runner for backward ensemble simulation."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.hindcast.models import HindcastReleaseAge, HindcastResult
from app.seeding.models import SeedingConfig, SeedingResult
from app.seeding.polygon import seed_from_polygon
from app.simulation.engine import DriftSimulationEngine
from app.simulation.models import SimulationConfig, SimulationDirection
from app.utils import generate_run_id, normalize_simulation_time

logger = logging.getLogger(__name__)


class HindcastRunner:
    """Runs backward ensemble for multiple release ages."""

    def __init__(self, engine: DriftSimulationEngine):
        """Initialize with simulation engine."""
        self.engine = engine

    def run_hindcast(
        self,
        run_id: str,
        observation_time: datetime,
        spill_polygon_geojson: dict,
        release_ages_hours: list[int],
        readers: list,
        seeding_config: SeedingConfig,
    ) -> HindcastResult:
        """
        Run backward ensemble for multiple release ages.

        Args:
            run_id: Phase 2 run ID
            observation_time: Time spill was observed
            spill_polygon_geojson: GeoJSON polygon
            release_ages_hours: List of candidate release ages
            readers: OpenDrift readers
            seeding_config: Particle seeding config

        Returns:
            HindcastResult with all candidates
        """
        logger.info(f"Starting hindcast for {len(release_ages_hours)} release ages")
        logger.info(f"Observation time: {observation_time.isoformat()}")

        observation_time_norm = normalize_simulation_time(
            observation_time, "observation_time"
        )

        # Seed particles at observation time
        seeding_result = seed_from_polygon(
            spill_polygon_geojson,
            observation_time_norm,
            seeding_config,
        )

        logger.info(f"Seeded {seeding_result.effective_particle_count} particles")

        release_ages = []

        for release_age_hours in release_ages_hours:
            logger.info(f"\nRunning hindcast for release age {release_age_hours}h")

            try:
                # Calculate simulation window
                release_time = observation_time_norm - timedelta(
                    hours=release_age_hours
                )

                # Create simulation config
                sim_config = SimulationConfig(
                    direction=SimulationDirection.BACKWARD,
                    start_time=observation_time_norm,
                    end_time=release_time,
                    initial_lats=seeding_result.get_initial_lats().tolist(),
                    initial_lons=seeding_result.get_initial_lons().tolist(),
                )

                # Run simulation
                sim_id = f"{run_id}-BACKWARD-{release_age_hours}H"
                sim_result = self.engine.run_simulation(
                    sim_config, readers, sim_id
                )

                release_ages.append(
                    HindcastReleaseAge(
                        release_age_hours=release_age_hours,
                        simulation_result=sim_result,
                    )
                )

                logger.info(f"Hindcast for {release_age_hours}h completed")

            except Exception as e:
                logger.error(f"Hindcast for {release_age_hours}h failed: {e}")
                release_ages.append(
                    HindcastReleaseAge(
                        release_age_hours=release_age_hours,
                        simulation_result=None,
                    )
                )

        result = HindcastResult(
            run_id=run_id,
            observation_time=observation_time_norm,
            release_ages=release_ages,
        )

        logger.info(f"Hindcast complete: {len(release_ages)} release ages processed")

        return result