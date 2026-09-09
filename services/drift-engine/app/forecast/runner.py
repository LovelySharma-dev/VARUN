"""Forecast runner for future drift prediction."""

import logging
from datetime import timedelta
from typing import Optional

from app.reconstruction.models import ReconstructionResult
from app.simulation.engine import DriftSimulationEngine
from app.simulation.models import SimulationConfig, SimulationDirection, SimulationResult
from app.utils import normalize_simulation_time

logger = logging.getLogger(__name__)


class ForecastRunner:
    """Runs future forecast from reconstruction."""

    def __init__(self, engine: DriftSimulationEngine):
        """Initialize with simulation engine."""
        self.engine = engine

    def run_forecast(
        self,
        run_id: str,
        reconstruction: ReconstructionResult,
        forecast_hours: float,
        readers: list,
    ) -> Optional[SimulationResult]:
        """
        Run forward forecast from reconstruction final positions.

        Args:
            run_id: Phase 2 run ID
            reconstruction: ReconstructionResult
            forecast_hours: Duration of forecast (hours)
            readers: OpenDrift readers

        Returns:
            SimulationResult with forecast trajectory
        """
        logger.info(f"Running {forecast_hours}h forecast")

        reconstruction_sim = reconstruction.simulation_result
        final_lats, final_lons = reconstruction_sim.get_final_positions()

        observation_time = reconstruction_sim.end_time
        forecast_end_time = observation_time + timedelta(hours=forecast_hours)

        logger.info(f"Forecast window: {observation_time.isoformat()} → {forecast_end_time.isoformat()}")

        # Create forecast simulation config
        forecast_config = SimulationConfig(
            direction=SimulationDirection.FORWARD,
            start_time=observation_time,
            end_time=forecast_end_time,
            initial_lats=final_lats.tolist(),
            initial_lons=final_lons.tolist(),
        )

        try:
            forecast_id = f"{run_id}-FORECAST"
            forecast_result = self.engine.run_simulation(
                forecast_config, readers, forecast_id
            )
            logger.info("Forecast simulation completed")
            return forecast_result
        except Exception as e:
            logger.error(f"Forecast simulation failed: {e}")
            return None