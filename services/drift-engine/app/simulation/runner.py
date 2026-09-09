"""
Phase 2 orchestration runner.

Coordinates:

1. Forcing reader creation
2. Spill polygon particle seeding
3. Backward reconstruction for candidate release ages
4. Release-age ranking
5. Forward forecast
6. Phase 2 -> Phase 3 search-window generation
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np

from app.config import Phase2Settings
from app.contracts.phase2_models import (
    Centroid,
    ForecastInfo,
    Observation,
    OriginRegion,
    Phase2SearchWindow,
    SearchWindow,
)
from app.forcing.readers import create_combined_readers
from app.forcing.models import ForcingConfig
from app.seeding.models import SeedingConfig
from app.seeding.polygon import seed_from_polygon
from app.simulation.engine import DriftSimulationEngine
from app.simulation.models import SimulationConfig, SimulationDirection
from app.utils import generate_run_id, haversine_distance, normalize_simulation_time

logger = logging.getLogger(__name__)


class Phase2Runner:
    """
    High-level Phase 2 workflow orchestrator.

    The runner coordinates forcing, seeding, simulation,
    ranking and Phase 3 handoff generation.
    """

    def __init__(self, settings: Phase2Settings):
        self.settings = settings

        self.output_dir = Path(settings.output_dir)
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.info(
            f"Phase2Runner initialized. "
            f"Output directory: {self.output_dir}"
        )

    def run_phase2(
        self,
        case_id: str,
        scene_id: Optional[str],
        observation_time: datetime,
        spill_polygon_geojson: dict,
        forcing_config: ForcingConfig,
        particle_count: int,
        release_ages_hours: Optional[list[int]],
        forecast_hours: float,
    ) -> dict:
        """
        Execute complete Phase 2 workflow.

        Returns a dictionary suitable for the FastAPI response.
        """

        run_id = generate_run_id()

        logger.info(
            f"Starting Phase 2 run {run_id} for case {case_id}"
        )

        try:
            # ---------------------------------------------------------
            # 1. Normalize observation time
            # ---------------------------------------------------------
            observation_time = normalize_simulation_time(
                observation_time,
                "observation_time",
            )

            # ---------------------------------------------------------
            # 2. Resolve configuration
            # ---------------------------------------------------------
            ages = (
                release_ages_hours
                if release_ages_hours
                else self.settings.release_ages_hours
            )

            forecast_duration = (
                forecast_hours
                if forecast_hours is not None
                else self.settings.forecast_duration_hours
            )

            if not ages:
                raise ValueError(
                    "No release age candidates provided"
                )

            if particle_count <= 0:
                raise ValueError(
                    "particle_count must be greater than zero"
                )

            # ---------------------------------------------------------
            # 3. Create forcing readers
            # ---------------------------------------------------------
            logger.info("Creating forcing readers")

            readers = create_combined_readers(
                current_file=forcing_config.current_file,
                wind_file=forcing_config.wind_file,
                combined_file=forcing_config.combined_file,
            )

            logger.info(
                f"Forcing readers ready: {len(readers)}"
            )

            # ---------------------------------------------------------
            # 4. Create seeding configuration
            # ---------------------------------------------------------
            seeding_config = SeedingConfig(
                particle_count=particle_count,
                seed_buffer_km=self.settings.seed_buffer_km,
                random_seed=self.settings.random_seed,
            )

            # ---------------------------------------------------------
            # 5. Run backward reconstruction candidates
            # ---------------------------------------------------------
            candidates = []

            for release_age in ages:

                logger.info(
                    f"Running release-age candidate: "
                    f"{release_age} hours"
                )

                candidate = self._run_backward_candidate(
                    observation_time=observation_time,
                    release_age_hours=release_age,
                    spill_polygon_geojson=spill_polygon_geojson,
                    seeding_config=seeding_config,
                    readers=readers,
                    run_id=run_id,
                )

                candidates.append(candidate)

            # ---------------------------------------------------------
            # 6. Rank candidate release ages
            # ---------------------------------------------------------
            best_candidate = self._rank_candidates(
                candidates
            )

            logger.info(
                f"Best release age: "
                f"{best_candidate['release_age_hours']} hours"
            )

            # ---------------------------------------------------------
            # 7. Calculate origin
            # ---------------------------------------------------------
            origin_lat = best_candidate["origin_lat"]
            origin_lon = best_candidate["origin_lon"]

            origin_radius_km = max(
                self.settings.density_grid_resolution_km,
                best_candidate["origin_radius_km"],
            )

            # ---------------------------------------------------------
            # 8. Forward forecast
            # ---------------------------------------------------------
            forecast_result = self._run_forecast(
                observation_time=observation_time,
                origin_lat=origin_lat,
                origin_lon=origin_lon,
                forecast_hours=forecast_duration,
                readers=readers,
                seeding_config=seeding_config,
                run_id=run_id,
            )

            # ---------------------------------------------------------
            # 9. Build Phase 3 search window
            # ---------------------------------------------------------
            search_window = self._build_search_window(
                observation_time=observation_time,
                origin_lat=origin_lat,
                origin_lon=origin_lon,
                radius_km=origin_radius_km,
                release_age_hours=best_candidate[
                    "release_age_hours"
                ],
            )

            # ---------------------------------------------------------
            # 10. Write Phase 2 -> Phase 3 contract
            # ---------------------------------------------------------
            artifacts = self._write_artifacts(
                run_id=run_id,
                case_id=case_id,
                scene_id=scene_id,
                observation_time=observation_time,
                best_candidate=best_candidate,
                origin_lat=origin_lat,
                origin_lon=origin_lon,
                origin_radius_km=origin_radius_km,
                search_window=search_window,
                forecast_result=forecast_result,
            )

            logger.info(
                f"Phase 2 run {run_id} completed successfully"
            )

            return {
                "run_id": run_id,
                "case_id": case_id,
                "status": "SUCCESS",
                "best_release_age_hours": best_candidate[
                    "release_age_hours"
                ],
                "origin": {
                    "lat": origin_lat,
                    "lon": origin_lon,
                    "radius_km": origin_radius_km,
                },
                "artifacts": artifacts,
            }

        except Exception as e:

            logger.exception(
                f"Phase 2 run {run_id} failed"
            )

            return {
                "run_id": run_id,
                "case_id": case_id,
                "status": "FAILED",
                "error": str(e),
            }

    # =================================================================
    # BACKWARD RECONSTRUCTION
    # =================================================================

    def _run_backward_candidate(
        self,
        observation_time: datetime,
        release_age_hours: int,
        spill_polygon_geojson: dict,
        seeding_config: SeedingConfig,
        readers: list,
        run_id: str,
    ) -> dict:
        """
        Run one backward candidate simulation.

        Particles are initialized inside the observed spill polygon
        at observation time and traced backward.
        """

        release_time = (
            observation_time
            - timedelta(hours=release_age_hours)
        )

        # Seed particles at observed spill location.
        seeding = seed_from_polygon(
            polygon_geojson=spill_polygon_geojson,
            seeding_time=observation_time,
            config=seeding_config,
        )

        initial_lats = seeding.get_initial_lats()
        initial_lons = seeding.get_initial_lons()

        config = SimulationConfig(
            direction=SimulationDirection.BACKWARD,
            start_time=observation_time,
            end_time=release_time,
            initial_lats=initial_lats.tolist(),
            initial_lons=initial_lons.tolist(),
            time_step_hours=self.settings.simulation_time_step_hours,
            output_interval_hours=self.settings.output_interval_hours,
        )

        engine = DriftSimulationEngine()

        result = engine.run_simulation(
            config=config,
            readers=readers,
            simulation_id=(
                f"{run_id}-BACKWARD-{release_age_hours}H"
            ),
        )

        final_lats, final_lons = (
            result.get_final_positions()
        )

        if len(final_lats) == 0:
            raise RuntimeError(
                f"No particles available after "
                f"{release_age_hours}h backward simulation"
            )

        # Calculate centroid of reconstructed origins.
        origin_lat = float(
            np.mean(final_lats)
        )

        origin_lon = float(
            np.mean(final_lons)
        )

        # Calculate radial spread around centroid.
        distances = np.array(
            [
                haversine_distance(
                    origin_lat,
                    origin_lon,
                    float(lat),
                    float(lon),
                )
                for lat, lon in zip(
                    final_lats,
                    final_lons,
                )
            ]
        )

        origin_radius_km = float(
            np.percentile(distances, 90)
        )

        # Basic deterministic score.
        #
        # This is intentionally a simple baseline.
        # A future scientific ranking layer can replace it
        # with polygon overlap / probability-density scoring.
        spread_score = 1.0 / (
            1.0 + origin_radius_km
        )

        return {
            "release_age_hours": release_age_hours,
            "origin_lat": origin_lat,
            "origin_lon": origin_lon,
            "origin_radius_km": origin_radius_km,
            "score": spread_score,
            "particle_count": result.particle_count,
            "time_steps": result.time_steps,
            "result": result,
        }

    # =================================================================
    # RANKING
    # =================================================================

    def _rank_candidates(
        self,
        candidates: list[dict],
    ) -> dict:
        """Rank release-age candidates."""

        if not candidates:
            raise ValueError(
                "No reconstruction candidates available"
            )

        ranked = sorted(
            candidates,
            key=lambda item: item["score"],
            reverse=True,
        )

        return ranked[0]

    # =================================================================
    # FORECAST
    # =================================================================

    def _run_forecast(
        self,
        observation_time: datetime,
        origin_lat: float,
        origin_lon: float,
        forecast_hours: float,
        readers: list,
        seeding_config: SeedingConfig,
        run_id: str,
    ) -> dict:
        """
        Run forward forecast from reconstructed origin.
        """

        # For forecast we use a point-centered seed region.
        from app.seeding.polygon import seed_from_point

        seeding = seed_from_point(
            centroid_lat=origin_lat,
            centroid_lon=origin_lon,
            radius_km=max(
                self.settings.density_grid_resolution_km,
                1.0,
            ),
            seeding_time=observation_time,
            config=seeding_config,
        )

        start_time = observation_time

        end_time = (
            observation_time
            + timedelta(hours=forecast_hours)
        )

        config = SimulationConfig(
            direction=SimulationDirection.FORWARD,
            start_time=start_time,
            end_time=end_time,
            initial_lats=seeding.get_initial_lats().tolist(),
            initial_lons=seeding.get_initial_lons().tolist(),
            time_step_hours=self.settings.simulation_time_step_hours,
            output_interval_hours=self.settings.output_interval_hours,
        )

        engine = DriftSimulationEngine()

        result = engine.run_simulation(
            config=config,
            readers=readers,
            simulation_id=f"{run_id}-FORECAST",
        )

        final_lats, final_lons = (
            result.get_final_positions()
        )

        forecast_path = (
            self.output_dir
            / run_id
            / "forecast.npz"
        )

        forecast_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        np.savez(
            forecast_path,
            latitudes=final_lats,
            longitudes=final_lons,
        )

        return {
            "result": result,
            "artifact": str(forecast_path),
        }

    # =================================================================
    # SEARCH WINDOW
    # =================================================================

    def _build_search_window(
        self,
        observation_time: datetime,
        origin_lat: float,
        origin_lon: float,
        radius_km: float,
        release_age_hours: int,
    ) -> SearchWindow:
        """
        Build spatial-temporal search window for Phase 3.
        """

        # Approximate conversion.
        lat_delta = radius_km / 111.0

        # Protect against division by zero near poles.
        cos_lat = max(
            abs(np.cos(np.radians(origin_lat))),
            0.01,
        )

        lon_delta = (
            radius_km
            / (111.0 * cos_lat)
        )

        start_time = (
            observation_time
            - timedelta(hours=release_age_hours)
        )

        end_time = (
            observation_time
            + timedelta(
                hours=self.settings.forecast_duration_hours
            )
        )

        return SearchWindow(
            min_lon=origin_lon - lon_delta,
            max_lon=origin_lon + lon_delta,
            min_lat=origin_lat - lat_delta,
            max_lat=origin_lat + lat_delta,
            start_time=start_time,
            end_time=end_time,
        )

    # =================================================================
    # ARTIFACTS
    # =================================================================

    def _write_artifacts(
        self,
        run_id: str,
        case_id: str,
        scene_id: Optional[str],
        observation_time: datetime,
        best_candidate: dict,
        origin_lat: float,
        origin_lon: float,
        origin_radius_km: float,
        search_window: SearchWindow,
        forecast_result: dict,
    ) -> list[str]:
        """Write Phase 2 output artifacts."""

        run_dir = (
            self.output_dir
            / run_id
        )

        run_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        search_window_path = (
            run_dir
            / "phase2-search-window.json"
        )

        forecast_path = Path(
            forecast_result["artifact"]
        )

        contract = Phase2SearchWindow(
            case_id=case_id,
            scene_id=scene_id,
            generated_at=datetime.utcnow(),
            observation=Observation(
                acquired_at=observation_time,
            ),
            best_release_age_hours=(
                best_candidate[
                    "release_age_hours"
                ]
            ),
            origin=OriginRegion(
                centroid=Centroid(
                    lon=origin_lon,
                    lat=origin_lat,
                ),
                radius_km=origin_radius_km,
            ),
            search_window=search_window,
            forecast=ForecastInfo(
                artifact=str(forecast_path),
                forecast_hours=(
                    self.settings.forecast_duration_hours
                ),
            ),
            artifacts=[],
            random_seed=self.settings.random_seed,
            phase2_run_id=run_id,
        )

        # Add artifact references.
        artifacts = [
            str(search_window_path),
            str(forecast_path),
        ]

        contract.artifacts = artifacts

        search_window_path.write_text(
            contract.model_dump_json(
                indent=2
            ),
            encoding="utf-8",
        )

        manifest_path = (
            run_dir
            / "phase2-artifact-manifest.json"
        )

        manifest = {
            "contract_version": (
                "phase2-artifact-manifest-v1"
            ),
            "run_id": run_id,
            "case_id": case_id,
            "status": "SUCCESS",
            "created_at": datetime.utcnow().isoformat(),
            "artifacts": [
                {
                    "type": "phase2_search_window",
                    "path": str(search_window_path),
                    "format": "json",
                    "size_bytes": search_window_path.stat().st_size,
                },
                {
                    "type": "forecast",
                    "path": str(forecast_path),
                    "format": "npz",
                    "size_bytes": forecast_path.stat().st_size,
                },
            ],
        }

        manifest_path.write_text(
            json.dumps(
                manifest,
                indent=2,
            ),
            encoding="utf-8",
        )

        artifacts.append(
            str(manifest_path)
        )

        return artifacts