"""
OpenDrift simulation engine for Phase 2.

Encapsulates the OpenDrift/OpenOil simulation logic.
"""

import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import xarray as xr
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
        self.o: Optional[OpenOil] = None

    def _configure_openoil(self, readers: list) -> OpenOil:
        """
        Create and configure an OpenOil instance.

        The Phase-2 simulation requires ocean-current and wind forcing.
        OpenOil may additionally request wave height, which is allowed
        to fall back to zero when no wave reader is supplied.
        """

        oil = OpenOil(loglevel=logging.INFO)

        for reader in readers:
            oil.add_reader(reader)
            logger.info("Added reader: %s", reader)

        try:
            oil.set_config(
                "environment:fallback:x_wind",
                0.0,
            )
            oil.set_config(
                "environment:fallback:y_wind",
                0.0,
            )
            oil.set_config(
                "environment:fallback:sea_surface_wave_significant_height",
                0.0,
            )
        except Exception as exc:
            logger.warning(
                "Could not set one or more environmental fallbacks: %s",
                exc,
            )

        try:
            required = getattr(oil, "required_variables", None)
            logger.info("OpenOil required variables: %s", required)
        except Exception:
            pass

        try:
            environment = getattr(oil, "environment", None)
            if environment is not None:
                logger.info(
                    "OpenOil environment variables: %s",
                    getattr(environment, "variables", None),
                )
        except Exception:
            pass

        return oil

    def _validate_configuration(
        self,
        config: SimulationConfig,
        readers: list,
    ) -> None:
        """Validate simulation configuration before starting OpenDrift."""

        if not readers:
            raise ValueError("No OpenDrift readers were supplied.")

        if len(config.initial_lats) == 0:
            raise ValueError("No initial particle latitudes supplied.")

        if len(config.initial_lons) == 0:
            raise ValueError("No initial particle longitudes supplied.")

        if len(config.initial_lats) != len(config.initial_lons):
            raise ValueError(
                "Initial latitude/longitude arrays have different lengths: "
                f"{len(config.initial_lats)} != {len(config.initial_lons)}"
            )

        if config.time_step_hours <= 0:
            raise ValueError(
                f"time_step_hours must be > 0, got {config.time_step_hours}"
            )

        if config.output_interval_hours <= 0:
            raise ValueError(
                "output_interval_hours must be > 0, "
                f"got {config.output_interval_hours}"
            )

        if config.start_time == config.end_time:
            raise ValueError("Simulation start_time and end_time are identical.")

        logger.info(
            "Configuration validated: particles=%d, timestep=%sh, "
            "output_interval=%sh, direction=%s",
            len(config.initial_lats),
            config.time_step_hours,
            config.output_interval_hours,
            config.direction.value,
        )

    def run_simulation(
        self,
        config: SimulationConfig,
        readers: list,
        simulation_id: str,
    ) -> SimulationResult:
        """
        Execute a drift simulation.

        Args:
            config: SimulationConfig containing initialization and timing.
            readers: List of OpenDrift reader objects.
            simulation_id: Unique ID for this simulation.

        Returns:
            SimulationResult containing trajectory data.

        Raises:
            SimulationExecutionError: If simulation fails.
        """

        logger.info(
            "Starting %s simulation %s",
            config.direction.value,
            simulation_id,
        )

        logger.info(
            "Time window: %s -> %s",
            config.start_time.isoformat(),
            config.end_time.isoformat(),
        )

        logger.info(
            "Particles: %d",
            len(config.initial_lats),
        )

        self._validate_configuration(config, readers)

        outfile_path: Optional[str] = None

        try:

            start_time_norm = normalize_simulation_time(
                config.start_time,
                "start_time",
            )

            end_time_norm = normalize_simulation_time(
                config.end_time,
                "end_time",
            )

            logger.info(
                "Normalized simulation time: %s -> %s",
                start_time_norm,
                end_time_norm,
            )

            tmpfile = tempfile.NamedTemporaryFile(
                suffix=".nc",
                delete=False,
            )

            outfile_path = tmpfile.name
            tmpfile.close()

            logger.info(
                "Temporary OpenDrift output: %s",
                outfile_path,
            )

            self.o = self._configure_openoil(readers)

            lats_array = np.asarray(
                config.initial_lats,
                dtype=float,
            )

            lons_array = np.asarray(
                config.initial_lons,
                dtype=float,
            )

            if not np.all(np.isfinite(lats_array)):
                raise ValueError("Initial latitude array contains NaN/Inf.")

            if not np.all(np.isfinite(lons_array)):
                raise ValueError("Initial longitude array contains NaN/Inf.")

            logger.info(
                "Seeding %d particles at %s",
                len(lats_array),
                start_time_norm.isoformat(),
            )

            logger.info(
                "Seed longitude range: %.6f -> %.6f",
                float(np.min(lons_array)),
                float(np.max(lons_array)),
            )

            logger.info(
                "Seed latitude range: %.6f -> %.6f",
                float(np.min(lats_array)),
                float(np.max(lats_array)),
            )

            self.o.seed_elements(
                lon=lons_array,
                lat=lats_array,
                time=start_time_norm,
            )

            duration = end_time_norm - start_time_norm

            if config.direction == SimulationDirection.BACKWARD:
                duration = -abs(duration)
            else:
                duration = abs(duration)

            if duration.total_seconds() == 0:
                raise ValueError("Calculated simulation duration is zero.")

            time_step_seconds = int(
                round(config.time_step_hours * 3600)
            )

            time_step_output = int(
                round(config.output_interval_hours * 3600)
            )

            if time_step_seconds <= 0:
                raise ValueError(
                    f"Calculated time_step is invalid: {time_step_seconds}"
                )

            if time_step_output <= 0:
                raise ValueError(
                    f"Calculated time_step_output is invalid: {time_step_output}"
                )

            # OpenDrift requires the timestep sign to match the duration sign.
            if config.direction == SimulationDirection.BACKWARD:
                time_step = -abs(time_step_seconds)
            else:
                time_step = abs(time_step_seconds)

            logger.info(
                "OpenDrift timestep: %d seconds",
                time_step,
            )

            logger.info(
                "OpenDrift output interval: %d seconds",
                time_step_output,
            )

            logger.info(
                "OpenDrift duration: %s",
                duration,
            )


            logger.info(
                "Running OpenOil simulation..."
            )

            self.o.run(
                time_step=time_step,
                time_step_output=time_step_output,
                duration=duration,
                outfile=outfile_path,
            )

            logger.info(
                "OpenOil run returned successfully."
            )


            if not Path(outfile_path).exists():
                raise RuntimeError(
                    f"OpenDrift did not create output file: {outfile_path}"
                )

            output_size = Path(outfile_path).stat().st_size

            logger.info(
                "OpenDrift output created: %d bytes",
                output_size,
            )

            if output_size == 0:
                raise RuntimeError(
                    "OpenDrift created an empty NetCDF output file."
                )


            result = self._extract_trajectory_from_file(
                outfile_path=outfile_path,
                config=config,
                start_time=start_time_norm,
                end_time=end_time_norm,
                simulation_id=simulation_id,
            )

            logger.info(
                "Simulation %s completed: %d particles, %d time steps",
                simulation_id,
                result.particle_count,
                result.time_steps,
            )

            return result

        except SimulationExecutionError:
            raise

        except Exception as exc:
            logger.exception(
                "OpenDrift simulation %s failed",
                simulation_id,
            )

            raise SimulationExecutionError(
                f"OpenDrift simulation failed: {exc}",
                details={
                    "simulation_id": simulation_id,
                    "direction": config.direction.value,
                    "start_time": config.start_time.isoformat(),
                    "end_time": config.end_time.isoformat(),
                },
            ) from exc

        finally:

            if outfile_path:
                try:
                    path = Path(outfile_path)

                    if path.exists():
                        path.unlink()

                        logger.debug(
                            "Deleted temporary output: %s",
                            outfile_path,
                        )

                except Exception as exc:
                    logger.warning(
                        "Could not delete temporary file %s: %s",
                        outfile_path,
                        exc,
                    )

            # Release OpenOil instance
            self.o = None

    def _extract_trajectory_from_file(
        self,
        outfile_path: str,
        config: SimulationConfig,
        start_time: datetime,
        end_time: datetime,
        simulation_id: str,
    ) -> SimulationResult:
        """
        Extract trajectory data from OpenDrift NetCDF output file.
        """

        path = Path(outfile_path)

        if not path.exists():
            raise RuntimeError(
                f"Output file not found: {outfile_path}"
            )

        logger.info(
            "Reading OpenDrift output: %s",
            outfile_path,
        )

        ds = xr.open_dataset(outfile_path)

        try:

            required_variables = {"lon", "lat", "time"}

            missing_variables = [
                variable
                for variable in required_variables
                if variable not in ds
            ]

            if missing_variables:
                raise RuntimeError(
                    "OpenDrift output is missing required variables: "
                    f"{missing_variables}"
                )

            logger.info(
                "Output dimensions: %s",
                dict(ds.sizes),
            )

            logger.info(
                "Output variables: %s",
                list(ds.data_vars),
            )


            lons_raw = np.asarray(ds["lon"].values)
            lats_raw = np.asarray(ds["lat"].values)

            logger.info(
                "Raw longitude shape: %s",
                lons_raw.shape,
            )

            logger.info(
                "Raw latitude shape: %s",
                lats_raw.shape,
            )

            if lons_raw.ndim != 2 or lats_raw.ndim != 2:
                raise RuntimeError(
                    "Expected OpenDrift lon/lat arrays to be 2-dimensional. "
                    f"Got lon={lons_raw.ndim}D, lat={lats_raw.ndim}D."
                )

            if lons_raw.shape != lats_raw.shape:
                raise RuntimeError(
                    "Longitude and latitude shapes differ: "
                    f"{lons_raw.shape} != {lats_raw.shape}"
                )

            lons = lons_raw.T
            lats = lats_raw.T


            times_data = np.asarray(ds["time"].values)

            logger.info(
                "Raw time shape: %s",
                times_data.shape,
            )

            if times_data.ndim != 1:
                times_data = times_data.reshape(-1)

            if len(times_data) != lons.shape[0]:
                raise RuntimeError(
                    "Time dimension does not match trajectory dimension: "
                    f"time={len(times_data)}, trajectory={lons.shape[0]}"
                )

            trajectory_times = [
                normalize_simulation_time(
                    timestamp,
                    "trajectory_time",
                )
                for timestamp in times_data
            ]

            finite_positions = (
                np.isfinite(lons) &
                np.isfinite(lats)
            )

            valid_position_count = int(
                np.count_nonzero(finite_positions)
            )

            logger.info(
                "Valid trajectory positions: %d / %d",
                valid_position_count,
                lons.size,
            )

            if valid_position_count == 0:
                raise RuntimeError(
                    "OpenDrift produced no valid particle positions."
                )

            particle_status = None

            if "status" in ds.data_vars:
                status_raw = np.asarray(
                    ds["status"].values
                )

                logger.info(
                    "Raw particle status shape: %s",
                    status_raw.shape,
                )

                if status_raw.ndim == 2:
                    particle_status = status_raw.T
                else:
                    particle_status = status_raw

            result = SimulationResult(
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
                "SimulationResult created successfully: "
                "particles=%d, time_steps=%d",
                result.particle_count,
                result.time_steps,
            )

            return result

        finally:
            ds.close()