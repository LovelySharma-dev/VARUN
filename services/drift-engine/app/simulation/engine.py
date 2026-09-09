"""
OpenDrift simulation engine for Phase 2.

Encapsulates the OpenDrift simulation logic.
"""

import logging
from datetime import datetime, timedelta

import numpy as np
from opendrift.models.openoil import OpenOil

from app.exceptions import SimulationExecutionError
from app.simulation.models import (
    SimulationConfig,
    SimulationDirection,
    SimulationResult,
    SimulationStatus,
)
from app.utils import normalize_simulation_time

logger = logging.getLogger(__name__)


class DriftSimulationEngine:
    """
    High-level OpenDrift simulation engine.

    Handles particle drift simulation for oil spills.
    """

    def __init__(self) -> None:
        """Initialize the simulation engine."""
        self.o = None

    def run_simulation(
        self,
        config: SimulationConfig,
        readers: list,
        simulation_id: str,
    ) -> SimulationResult:
        """
        Execute a drift simulation.

        Args:
            config: Simulation configuration.
            readers: List of OpenDrift reader objects.
            simulation_id: Unique simulation ID.

        Returns:
            SimulationResult containing trajectory data.

        Raises:
            SimulationExecutionError: If simulation fails.
        """

        logger.info(
            f"Starting {config.direction.value} simulation {simulation_id}"
        )

        logger.info(
            f"Time window: "
            f"{config.start_time.isoformat()} → "
            f"{config.end_time.isoformat()}"
        )

        logger.info(
            f"Particles: {len(config.initial_lats)}"
        )

        try:
            # ---------------------------------------------------------
            # 1. Normalize simulation times
            # ---------------------------------------------------------
            start_time = normalize_simulation_time(
                config.start_time,
                "start_time",
            )

            end_time = normalize_simulation_time(
                config.end_time,
                "end_time",
            )

            # ---------------------------------------------------------
            # 2. Create OpenOil model
            # ---------------------------------------------------------
            logger.info("Creating OpenOil model")

            self.o = OpenOil(
                loglevel=logging.INFO
            )

            logger.info("OpenOil model created successfully")

            # ---------------------------------------------------------
            # 3. Add environmental forcing readers
            # ---------------------------------------------------------
            if not readers:
                raise ValueError(
                    "No OpenDrift forcing readers provided"
                )

            for reader in readers:
                logger.info(
                    f"Adding forcing reader: {reader}"
                )

                self.o.add_reader(reader)

            logger.info(
                f"Added {len(readers)} forcing reader(s)"
            )

            # ---------------------------------------------------------
            # 4. Validate particle coordinates
            # ---------------------------------------------------------
            lats_array = np.asarray(
                config.initial_lats,
                dtype=float,
            )

            lons_array = np.asarray(
                config.initial_lons,
                dtype=float,
            )

            if len(lats_array) == 0:
                raise ValueError(
                    "No initial latitude coordinates provided"
                )

            if len(lons_array) == 0:
                raise ValueError(
                    "No initial longitude coordinates provided"
                )

            if len(lats_array) != len(lons_array):
                raise ValueError(
                    "Initial latitude and longitude arrays "
                    "must have the same length"
                )

            logger.info(
                f"Validated {len(lats_array)} particle positions"
            )

            # ---------------------------------------------------------
            # 5. Seed particles
            # ---------------------------------------------------------
            logger.info(
                f"Seeding {len(lats_array)} particles at "
                f"{start_time.isoformat()}"
            )

            self.o.seed_elements(
                lon=lons_array,
                lat=lats_array,
                time=start_time,
            )

            logger.info(
                "Particles seeded successfully"
            )

            # ---------------------------------------------------------
            # 6. Calculate simulation duration
            # ---------------------------------------------------------
            if config.direction == SimulationDirection.BACKWARD:

                duration = start_time - end_time

                if duration.total_seconds() <= 0:
                    raise ValueError(
                        "For backward simulation, "
                        "start_time must be later than end_time"
                    )

            else:

                duration = end_time - start_time

                if duration.total_seconds() <= 0:
                    raise ValueError(
                        "For forward simulation, "
                        "end_time must be later than start_time"
                    )

            # ---------------------------------------------------------
            # 7. Validate time settings
            # ---------------------------------------------------------
            if config.time_step_hours <= 0:
                raise ValueError(
                    "time_step_hours must be greater than zero"
                )

            if config.output_interval_hours <= 0:
                raise ValueError(
                    "output_interval_hours must be greater than zero"
                )

            time_step = timedelta(
                hours=config.time_step_hours
            )

            output_interval = timedelta(
                hours=config.output_interval_hours
            )

            logger.info(
                f"Simulation duration: {duration}"
            )

            logger.info(
                f"Time step: {time_step}"
            )

            logger.info(
                f"Output interval: {output_interval}"
            )

            # ---------------------------------------------------------
            # 8. Run OpenDrift
            #
            # IMPORTANT:
            # Do NOT pass start= or end=.
            # The simulation time is determined by:
            #
            #   seed_elements(time=...)
            #   +
            #   run(duration=...)
            # ---------------------------------------------------------
            logger.info(
                "Running OpenDrift simulation..."
            )

            if config.direction == SimulationDirection.BACKWARD:

                logger.info(
                    "Running BACKWARD simulation"
                )

                self.o.run(
                    duration=duration,
                    time_step=-time_step,
                    time_step_output=output_interval,
                    outfile=None,
                )

            else:

                logger.info(
                    "Running FORWARD simulation"
                )

                self.o.run(
                    duration=duration,
                    time_step=time_step,
                    time_step_output=output_interval,
                    outfile=None,
                )

            logger.info(
                "OpenDrift simulation completed successfully"
            )

            # ---------------------------------------------------------
            # 9. Extract trajectory
            # ---------------------------------------------------------
            result = self._extract_trajectory(
                config=config,
                start_time=start_time,
                end_time=end_time,
                simulation_id=simulation_id,
            )

            logger.info(
                f"Simulation {simulation_id} completed successfully"
            )

            return result

        except SimulationExecutionError:
            raise

        except Exception as e:

            logger.exception(
                f"Simulation {simulation_id} failed"
            )

            raise SimulationExecutionError(
                f"OpenDrift simulation failed: {e}",
                details={
                    "simulation_id": simulation_id,
                },
            ) from e

        finally:

            # Release OpenDrift object after extraction.
            self.o = None

    def _extract_trajectory(
        self,
        config: SimulationConfig,
        start_time: datetime,
        end_time: datetime,
        simulation_id: str,
    ) -> SimulationResult:
        """
        Extract trajectory data from OpenDrift result dataset.
        """

        if self.o is None:
            raise RuntimeError(
                "No active OpenDrift simulation"
            )

        # -------------------------------------------------------------
        # OpenDrift stores simulation output in `result`
        # -------------------------------------------------------------
        result_dataset = self.o.result

        if result_dataset is None:
            raise RuntimeError(
                "OpenDrift returned no result dataset"
            )

        # -------------------------------------------------------------
        # Validate required variables
        # -------------------------------------------------------------
        if "lon" not in result_dataset:
            raise RuntimeError(
                "OpenDrift result missing 'lon'"
            )

        if "lat" not in result_dataset:
            raise RuntimeError(
                "OpenDrift result missing 'lat'"
            )

        # -------------------------------------------------------------
        # Extract trajectory
        # -------------------------------------------------------------
        lons = np.asarray(
            result_dataset["lon"].values
        )

        lats = np.asarray(
            result_dataset["lat"].values
        )

        # -------------------------------------------------------------
        # Extract time coordinate
        # -------------------------------------------------------------
        if "time" in result_dataset.coords:

            times = result_dataset["time"].values

        elif "time" in result_dataset:

            times = result_dataset["time"].values

        else:

            raise RuntimeError(
                "OpenDrift result missing 'time'"
            )

        # -------------------------------------------------------------
        # Validate dimensions
        # -------------------------------------------------------------
        if lons.ndim != 2:
            raise RuntimeError(
                f"Unexpected longitude shape: {lons.shape}"
            )

        if lats.ndim != 2:
            raise RuntimeError(
                f"Unexpected latitude shape: {lats.shape}"
            )

        if lons.shape != lats.shape:
            raise RuntimeError(
                f"Latitude/longitude shape mismatch: "
                f"{lats.shape} vs {lons.shape}"
            )

        logger.info(
            f"Extracted trajectory: "
            f"{lons.shape[0]} time steps × "
            f"{lons.shape[1]} particles"
        )

        # -------------------------------------------------------------
        # Convert trajectory times
        # -------------------------------------------------------------
        trajectory_times = [
            normalize_simulation_time(
                time,
                "trajectory_time",
            )
            for time in times
        ]

        # -------------------------------------------------------------
        # Particle status
        # -------------------------------------------------------------
        particle_status = None

        if hasattr(self.o, "elements"):

            elements = self.o.elements

            if hasattr(elements, "status"):

                try:
                    particle_status = np.asarray(
                        elements.status
                    )
                except Exception:
                    logger.warning(
                        "Could not extract particle status"
                    )
                    particle_status = None

        # -------------------------------------------------------------
        # Create SimulationResult
        # -------------------------------------------------------------
        simulation_result = SimulationResult(
            simulation_id=simulation_id,
            config=config,
            status=SimulationStatus.COMPLETED,
            start_time=start_time,
            end_time=end_time,
            trajectory_times=trajectory_times,
            trajectory_lats=lats,
            trajectory_lons=lons,
            particle_status=particle_status,
        )

        logger.info(
            f"SimulationResult created: "
            f"{simulation_result.particle_count} particles, "
            f"{simulation_result.time_steps} time steps"
        )

        return simulation_result