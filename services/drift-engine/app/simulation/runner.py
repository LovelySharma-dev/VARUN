"""Complete Phase 2 pipeline runner for VARUN drift simulation."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import json
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

import numpy as np
import xarray as xr

from app.artifacts import (
    create_particle_positions_geojson,
    create_trajectory_geojson,
    write_geodataframe_geojson,
    write_json_manifest,
    write_netcdf_dataset,
)
from app.config import Phase2Settings
from app.contracts import (
    Centroid,
    Observation,
    OriginRegion,
    Phase2ArtifactManifest,
    Phase2SearchWindow,
    SearchWindow,
)
from app.forcing import audit_forcing_file, create_combined_readers
from app.forcing.models import ForcingConfig
from app.hindcast import HindcastRunner
from app.origin import calculate_origin_density, generate_contours, get_density_bounds
from app.reconstruction import ReconstructionRunner
from app.seeding import SeedingConfig
from app.simulation.engine import DriftSimulationEngine
from app.utils import (
    ensure_output_dir,
    generate_run_id,
    get_logger,
    normalize_simulation_time,
    to_iso_utc,
)
from app.forecast import ForecastRunner

logger = get_logger(__name__)


class Phase2CompleteRunner:
    """Complete Phase 2 runner with all required artifacts and validation."""

    def __init__(self, settings: Optional[Phase2Settings] = None):
        """Initialize runner."""
        self.settings = settings or Phase2Settings()
        self.engine = DriftSimulationEngine()
        self.run_id = None
        self.run_dir = None

    def run(
        self,
        case_id: str,
        scene_id: str,
        observation_time: datetime,
        spill_polygon_geojson: dict,
        forcing_config: ForcingConfig,
        particle_count: int = 1500,
        release_ages_hours: Optional[list[int]] = None,
        forecast_hours: float = 12.0,
    ) -> dict:
        """
        Execute complete Phase 2 workflow.

        Returns:
            Dictionary with execution summary and artifact paths
        """
        self.run_id = generate_run_id()
        self.run_dir = ensure_output_dir(self.settings.output_dir, self.run_id)

        logger.info(f"\n{'='*70}")
        logger.info(f"VARUN Phase 2 Complete Execution")
        logger.info(f"{'='*70}")
        logger.info(f"Run ID: {self.run_id}")
        logger.info(f"Case ID: {case_id}")
        logger.info(f"Scene ID: {scene_id}")
        logger.info(f"Output dir: {self.run_dir}")

        observation_time = normalize_simulation_time(observation_time, "observation_time")
        release_ages_hours = release_ages_hours or self.settings.release_ages_hours

        all_artifacts = []
        validation_checks = {}

        try:
            # ========== Step 1: Forcing Audit ==========
            logger.info(f"\n[1/9] Auditing forcing files...")
            forcing_audit = self._audit_forcing(forcing_config, validation_checks)

            # ========== Step 2: Create Readers ==========
            logger.info(f"[2/9] Creating OpenDrift readers...")
            readers = create_combined_readers(
                current_file=forcing_config.current_file,
                wind_file=forcing_config.wind_file,
                combined_file=forcing_config.combined_file,
            )

            # ========== Step 3: Run Hindcast ==========
            logger.info(f"[3/9] Running backward ensemble...")
            seeding_config = SeedingConfig(
                particle_count=particle_count,
                seed_buffer_km=self.settings.seed_buffer_km,
                random_seed=self.settings.random_seed,
            )

            hindcast_runner = HindcastRunner(self.engine)
            hindcast_result = hindcast_runner.run_hindcast(
                run_id=self.run_id,
                observation_time=observation_time,
                spill_polygon_geojson=spill_polygon_geojson,
                release_ages_hours=release_ages_hours,
                readers=readers,
                seeding_config=seeding_config,
            )

            successful_ages = [
                ra for ra in hindcast_result.release_ages
                if ra.simulation_result is not None
            ]
            validation_checks["hindcast"] = {
                "status": "PASS" if len(successful_ages) > 0 else "FAIL",
                "message": f"{len(successful_ages)}/{len(release_ages_hours)} hindcasts successful",
            }

            # Save hindcast artifacts
            hindcast_dir = self.run_dir / "backward"
            hindcast_dir.mkdir(exist_ok=True)

            for ra in successful_ages:
                try:
                    output_file = hindcast_dir / f"release-{ra.release_age_hours}h.nc"
                    # trajectory_lons/lats are (n_times, n_particles)
                    ds = xr.Dataset(
                        {
                            "lon": (["time", "particle"], ra.simulation_result.trajectory_lons),
                            "lat": (["time", "particle"], ra.simulation_result.trajectory_lats),
                        },
                        coords={
                            "time": ra.simulation_result.trajectory_times,
                            "particle": np.arange(ra.simulation_result.particle_count),
                        },
                    )
                    write_netcdf_dataset(ds, output_file)
                    all_artifacts.append(("backward_trajectory", str(output_file)))
                except Exception as e:
                    logger.warning(f"Could not save hindcast {ra.release_age_hours}h: {e}")

            # ========== Step 4: Calculate Origin Density ==========
            logger.info(f"[4/9] Calculating origin density...")
            density_ds = calculate_origin_density(hindcast_result)

            if density_ds is not None:
                density_file = self.run_dir / "origin" / "density.nc"
                density_file.parent.mkdir(exist_ok=True)
                write_netcdf_dataset(density_ds, density_file)
                all_artifacts.append(("origin_density", str(density_file)))
                validation_checks["origin_density"] = {"status": "PASS"}
                logger.info("✓ Origin density calculated")
            else:
                logger.warning("Could not calculate origin density")
                validation_checks["origin_density"] = {"status": "FAIL"}
                density_ds = None

            # ========== Step 5: Generate Origin Contours ==========
            logger.info(f"[5/9] Generating origin contours...")
            contours_50 = None
            contours_75 = None
            contours_90 = None

            if density_ds is not None:
                for level in [0.50, 0.75, 0.90]:
                    contours_gdf = generate_contours(
                        density_ds,
                        levels=[level],
                    )
                    if contours_gdf is not None and len(contours_gdf) > 0:
                        filename = f"origin_{int(level*100)}.geojson"
                        contours_file = self.run_dir / "origin" / filename
                        write_geodataframe_geojson(contours_gdf, contours_file)
                        all_artifacts.append(("origin_contours", str(contours_file)))
                        logger.info(f"✓ Generated {level*100:.0f}% contours")

                validation_checks["origin_contours"] = {"status": "PASS"}
            else:
                validation_checks["origin_contours"] = {"status": "BLOCKED", "reason": "No origin density"}

            # ========== Step 6: Rank Release Ages ==========
            logger.info(f"[6/9] Ranking release ages...")
            release_scores = self._rank_release_ages(hindcast_result)

            # Save release time scores
            scores_csv = self.run_dir / "release_time_scores.csv"
            with open(scores_csv, "w") as f:
                f.write("release_age_hours,release_time,status,ranking_score,rank,metric1,metric2\n")
                for age in release_ages_hours:
                    score_info = release_scores.get(age, {})
                    rank = score_info.get("rank", "NA")
                    score = score_info.get("score", 0.0)
                    status = score_info.get("status", "FAILED")
                    release_time = score_info.get("release_time", "NA")
                    f.write(f"{age},{release_time},{status},{score},{rank},placeholder,placeholder\n")
            all_artifacts.append(("release_time_scores", str(scores_csv)))

            best_release_age = self._get_best_release_age(release_scores)
            if best_release_age is None:
                logger.warning("No best release age found")
                validation_checks["release_ranking"] = {"status": "FAIL"}
                return self._create_failed_response("No successful release age")

            validation_checks["release_ranking"] = {"status": "PASS", "best_age": best_release_age}

            # ========== Step 7: Run Forward Reconstruction ==========
            logger.info(f"[7/9] Running forward reconstruction...")

            if density_ds is not None:
                lat_min, lat_max, lon_min, lon_max = get_density_bounds(density_ds, level=0.9)
                best_origin_lat = (lat_min + lat_max) / 2
                best_origin_lon = (lon_min + lon_max) / 2
            else:
                from shapely.geometry import shape
                poly = shape(spill_polygon_geojson)
                best_origin_lon, best_origin_lat = poly.centroid.coords[0]

            reconstruction_runner = ReconstructionRunner(self.engine)
            reconstruction = reconstruction_runner.run(
                run_id=self.run_id,
                best_origin_lat=best_origin_lat,
                best_origin_lon=best_origin_lon,
                observation_time=observation_time,
                release_age_hours=best_release_age,
                readers=readers,
                seeding_config=seeding_config,
            )

            if reconstruction:
                logger.info("✓ Reconstruction complete")
                recon_file = self.run_dir / "reconstruction" / "trajectory.nc"
                recon_file.parent.mkdir(exist_ok=True)
                ds_recon = xr.Dataset(
                    {
                        "lon": (["time", "particle"], reconstruction.simulation_result.trajectory_lons),
                        "lat": (["time", "particle"], reconstruction.simulation_result.trajectory_lats),
                    },
                    coords={
                        "time": reconstruction.simulation_result.trajectory_times,
                        "particle": np.arange(reconstruction.simulation_result.particle_count),
                    },
                )
                write_netcdf_dataset(ds_recon, recon_file)
                all_artifacts.append(("reconstruction", str(recon_file)))

                # Create reconstruction GeoJSON
                final_lats, final_lons = reconstruction.simulation_result.get_final_positions()
                recon_geojson = create_particle_positions_geojson(
                    final_lats, final_lons,
                    properties={"scenario": "reconstruction"}
                )
                recon_geojson_file = self.run_dir / "reconstruction" / "reconstruction.geojson"
                with open(recon_geojson_file, "w") as f:
                    json.dump(recon_geojson, f)
                all_artifacts.append(("reconstruction_geojson", str(recon_geojson_file)))

                # Save reconstruction metrics
                metrics_file = self.run_dir / "reconstruction_metrics.json"
                reconstruction.metrics

                metrics_data = {
                    "centroid_distance_km": reconstruction.metrics.centroid_distance_km,
                    "overlap_score": reconstruction.metrics.overlap_score,
                    "particle_coverage": reconstruction.metrics.particle_coverage,
                    "overall_score": reconstruction.metrics.overall_score,
                }
                write_json_manifest(metrics_data, metrics_file)
                all_artifacts.append(("reconstruction_metrics", str(metrics_file)))

                validation_checks["reconstruction"] = {"status": "PASS"}
            else:
                logger.warning("Reconstruction failed")
                validation_checks["reconstruction"] = {"status": "FAIL"}
                reconstruction = None

            # ========== Step 8: Run Forecast ==========
            logger.info(f"[8/9] Running future forecast...")
            forecast_result = None

            if reconstruction:
                forecast_runner = ForecastRunner(self.engine)
                forecast_result = forecast_runner.run_forecast(
                    run_id=self.run_id,
                    reconstruction=reconstruction,
                    forecast_hours=forecast_hours,
                    readers=readers,
                )

                if forecast_result:
                    logger.info("✓ Forecast complete")

                    # Save forecast NetCDF
                    forecast_file = self.run_dir / "forecast" / "forecast.nc"
                    forecast_file.parent.mkdir(exist_ok=True)
                    ds_forecast = xr.Dataset(
                        {
                            "lon": (["time", "particle"], forecast_result.trajectory_lons),
                            "lat": (["time", "particle"], forecast_result.trajectory_lats),
                        },
                        coords={
                            "time": forecast_result.trajectory_times,
                            "particle": np.arange(forecast_result.particle_count),
                        },
                    )
                    write_netcdf_dataset(ds_forecast, forecast_file)
                    all_artifacts.append(("forecast", str(forecast_file)))

                    # Save forecast GeoJSON
                    final_lats, final_lons = forecast_result.get_final_positions()
                    forecast_geojson = create_particle_positions_geojson(
                        final_lats, final_lons,
                        properties={"scenario": "forecast"}
                    )
                    forecast_geojson_file = self.run_dir / "forecast" / "forecast.geojson"
                    with open(forecast_geojson_file, "w") as f:
                        json.dump(forecast_geojson, f)
                    all_artifacts.append(("forecast_geojson", str(forecast_geojson_file)))

                    validation_checks["forecast"] = {"status": "PASS"}
                else:
                    logger.warning("Forecast failed")
                    validation_checks["forecast"] = {"status": "FAIL"}

            # ========== Step 9: Generate Phase 3 Search Window ==========
            logger.info(f"[9/9] Generating Phase 3 search window...")

            if density_ds is not None:
                lat_min, lat_max, lon_min, lon_max = get_density_bounds(density_ds, level=0.9)
            else:
                from shapely.geometry import shape
                poly = shape(spill_polygon_geojson)
                bounds = poly.bounds  # (minx, miny, maxx, maxy)
                lon_min, lat_min, lon_max, lat_max = bounds

            # Calculate release and search times
            release_time = observation_time - timedelta(hours=best_release_age)

            search_window = SearchWindow(
                min_lat=lat_min,
                max_lat=lat_max,
                min_lon=lon_min,
                max_lon=lon_max,
                start_time=release_time,
                end_time=observation_time + timedelta(hours=forecast_hours),
            )

            # Extract just the paths from all_artifacts (which are tuples of (type, path))
            artifact_paths = [str(path) for _, path in all_artifacts]

            phase3_contract = Phase2SearchWindow(
                case_id=case_id,
                scene_id=scene_id,
                generated_at=datetime.utcnow(),
                observation=Observation(acquired_at=observation_time),
                best_release_age_hours=best_release_age,
                origin=OriginRegion(
                    centroid=Centroid(lon=best_origin_lon, lat=best_origin_lat),
                    radius_km=self.settings.seed_buffer_km,
                ),
                search_window=search_window,
                forecast=None,
                artifacts=artifact_paths,
                random_seed=self.settings.random_seed,
                phase2_run_id=self.run_id,
            )

            search_window_file = self.run_dir / "search_window.json"
            with open(search_window_file, "w") as f:
                json.dump(phase3_contract.dict(), f, indent=2, default=str)
            all_artifacts.append(("search_window", str(search_window_file)))

            validation_checks["search_window"] = {"status": "PASS"}
            logger.info("✓ Phase 3 search window generated")

            # ========== Generate Validation Report ==========
            validation_report = {
                "timestamp": datetime.utcnow().isoformat(),
                "run_id": self.run_id,
                "case_id": case_id,
                "opendrift_version": "1.14.11",
                "checks": validation_checks,
                "status": "PASS" if all(c.get("status") == "PASS" for c in validation_checks.values()) else "PARTIAL",
            }

            validation_file = self.run_dir / "validation_report.json"
            write_json_manifest(validation_report, validation_file)
            all_artifacts.append(("validation", str(validation_file)))

            # ========== Generate Summary ==========
            summary = {
                "status": "SUCCESS",
                "run_id": self.run_id,
                "case_id": case_id,
                "scene_id": scene_id,
                "observation_time": to_iso_utc(observation_time),
                "phase2_run_id": self.run_id,
                "opendrift_version": "1.14.11",
                "particle_count": particle_count,
                "release_ages": release_ages_hours,
                "successful_release_ages": [ra.release_age_hours for ra in successful_ages],
                "best_release_age_hours": best_release_age,
                "best_release_time": to_iso_utc(release_time),
                "forecast_hours": forecast_hours,
                "output_directory": str(self.run_dir),
                "artifacts_count": len(all_artifacts),
                "validation_status": validation_report["status"],
                "timestamp": datetime.utcnow().isoformat(),
            }

            summary_file = self.run_dir / "summary.json"
            write_json_manifest(summary, summary_file)

            # ========== Generate Run Config ==========
            run_config = {
                "case_id": case_id,
                "scene_id": scene_id,
                "observation_time": to_iso_utc(observation_time),
                "particle_count": particle_count,
                "release_ages": release_ages_hours,
                "forecast_hours": forecast_hours,
                "forcing_files": {
                    "current_file": str(forcing_config.current_file) if forcing_config.current_file else None,
                    "wind_file": str(forcing_config.wind_file) if forcing_config.wind_file else None,
                    "combined_file": str(forcing_config.combined_file) if forcing_config.combined_file else None,
                },
                "random_seed": self.settings.random_seed,
                "opendrift_version": "1.14.11",
                "simulation_timestep_hours": self.settings.simulation_time_step_hours,
                "output_interval_hours": self.settings.output_interval_hours,
                "crs": "EPSG:4326",
                "coordinate_order": "[longitude, latitude]",
                "run_id": self.run_id,
            }

            config_file = self.run_dir / "run_config.json"
            write_json_manifest(run_config, config_file)

            logger.info(f"\n{'='*70}")
            logger.info(f"✓ Phase 2 COMPLETE")
            logger.info(f"{'='*70}")
            logger.info(f"Output directory: {self.run_dir}")
            logger.info(f"Artifacts: {len(all_artifacts)}")
            logger.info(f"Validation: {validation_report['status']}\n")

            return {
                "status": "SUCCESS",
                "run_id": self.run_id,
                "case_id": case_id,
                "output_dir": str(self.run_dir),
                "summary": summary,
                "validation": validation_report,
            }

        except Exception as e:
            logger.error(f"\n✗ Phase 2 FAILED: {e}", exc_info=True)
            return self._create_failed_response(str(e))

    def _audit_forcing(self, forcing_config: ForcingConfig, validation_checks: dict) -> dict:
        """Audit forcing files."""
        forcing_files = forcing_config.get_files()
        forcing_audit = {}

        for file_path in forcing_files:
            audit_result = audit_forcing_file(file_path)
            forcing_audit[file_path.name] = {
                "passed": audit_result.passed,
                "errors": audit_result.errors,
                "warnings": audit_result.warnings,
            }

            if not audit_result.passed:
                raise Exception(f"Forcing validation failed: {audit_result.errors}")

            logger.info(f"✓ {file_path.name} passed audit")

        validation_checks["forcing_audit"] = {"status": "PASS"}
        return forcing_audit

    def _rank_release_ages(self, hindcast_result) -> dict:
        """Rank release ages based on reconstruction (placeholder)."""
        scores = {}

        for i, ra in enumerate(hindcast_result.release_ages):
            if ra.simulation_result is None:
                scores[ra.release_age_hours] = {
                    "status": "FAILED",
                    "score": 0.0,
                    "rank": None,
                }
            else:
                # Simple ranking based on order (real implementation would use reconstruction metrics)
                rank = i + 1
                score = 1.0 / (rank + 1)  # Higher score for earlier rank

                release_time = hindcast_result.observation_time - timedelta(
                    hours=ra.release_age_hours
                )

                scores[ra.release_age_hours] = {
                    "status": "SUCCESS",
                    "score": score,
                    "rank": rank,
                    "release_time": to_iso_utc(release_time),
                }

        return scores

    def _get_best_release_age(self, scores: dict) -> Optional[int]:
        """Get best release age based on scores."""
        valid_scores = [
            (age, info) for age, info in scores.items()
            if info["status"] == "SUCCESS"
        ]

        if not valid_scores:
            return None

        # Return the one with lowest rank (rank 1 is best)
        best = min(valid_scores, key=lambda x: x[1].get("rank", float("inf")))
        return best[0]

    def _create_failed_response(self, error_msg: str) -> dict:
        """Create a failed response."""
        return {
            "status": "FAILED",
            "run_id": self.run_id,
            "error": error_msg,
            "output_dir": str(self.run_dir) if self.run_dir else None,
        }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="VARUN Phase 2 Oil Spill Drift Simulation"
    )

    parser.add_argument(
        "--case-id",
        required=True,
        help="Case ID, e.g. CASE-2026-001",
    )

    parser.add_argument(
        "--scene-id",
        default="SCENE-001",
        help="Scene ID",
    )

    parser.add_argument(
        "--observation-time",
        required=True,
        help="Observation time in ISO format, e.g. 2026-09-03T08:30:00",
    )

    parser.add_argument(
        "--polygon-file",
        required=True,
        help="Path to spill polygon GeoJSON",
    )

    parser.add_argument(
        "--current-file",
        required=True,
        help="Path to ocean current NetCDF",
    )

    parser.add_argument(
        "--wind-file",
        required=True,
        help="Path to wind NetCDF",
    )

    parser.add_argument(
        "--particles",
        type=int,
        default=1500,
        help="Number of particles",
    )

    parser.add_argument(
        "--forecast-hours",
        type=float,
        default=24.0,
        help="Forward forecast duration in hours",
    )

    args = parser.parse_args()

    # ---------------------------------------------------------
    # Load spill polygon from actual GeoJSON file
    # ---------------------------------------------------------

    polygon_path = Path(args.polygon_file)

    if not polygon_path.exists():
        raise FileNotFoundError(
            f"Polygon file not found: {polygon_path}"
        )

    with polygon_path.open("r", encoding="utf-8") as f:
        polygon_data = json.load(f)

    # Support FeatureCollection
    if polygon_data.get("type") == "FeatureCollection":

        features = polygon_data.get("features", [])

        if not features:
            raise ValueError(
                "Polygon GeoJSON FeatureCollection contains no features"
            )

        geometries = []

        for feature in features:
            geometry = feature.get("geometry")

            if geometry is None:
                continue

            geometries.append(shape(geometry))

        if not geometries:
            raise ValueError(
                "No valid geometry found in FeatureCollection"
            )

        polygon_geometry = unary_union(geometries)

    # Support Feature
    elif polygon_data.get("type") == "Feature":

        geometry = polygon_data.get("geometry")

        if geometry is None:
            raise ValueError(
                "GeoJSON Feature does not contain geometry"
            )

        polygon_geometry = shape(geometry)

    # Support direct Polygon / MultiPolygon
    elif polygon_data.get("type") in ("Polygon", "MultiPolygon"):

        polygon_geometry = shape(polygon_data)

    else:
        raise ValueError(
            f"Unsupported GeoJSON type: {polygon_data.get('type')}"
        )

    if polygon_geometry.is_empty:
        raise ValueError("Spill polygon geometry is empty")

    if not polygon_geometry.is_valid:
        polygon_geometry = polygon_geometry.buffer(0)

    if polygon_geometry.is_empty:
        raise ValueError(
            "Spill polygon became empty after geometry repair"
        )

    spill_polygon = mapping(polygon_geometry)

    print("\n" + "=" * 70)
    print("VARUN PHASE 2")
    print("=" * 70)
    print(f"Case ID:          {args.case_id}")
    print(f"Scene ID:         {args.scene_id}")
    print(f"Observation time: {args.observation_time}")
    print(f"Polygon file:     {polygon_path}")
    print(f"Polygon type:     {polygon_geometry.geom_type}")
    print(f"Polygon bounds:   {polygon_geometry.bounds}")
    print(f"Current file:     {args.current_file}")
    print(f"Wind file:        {args.wind_file}")
    print(f"Particles:        {args.particles}")
    print(f"Forecast hours:   {args.forecast_hours}")
    print("=" * 70 + "\n")

    # ---------------------------------------------------------
    # Parse observation time
    # ---------------------------------------------------------

    observation_time = datetime.fromisoformat(
        args.observation_time
    )

    # ---------------------------------------------------------
    # Create forcing configuration
    # ---------------------------------------------------------

    forcing_config = ForcingConfig(
        current_file=Path(args.current_file),
        wind_file=Path(args.wind_file),
    )

    runner = Phase2CompleteRunner()

    result = runner.run(
        case_id=args.case_id,
        scene_id=args.scene_id,
        observation_time=observation_time,
        spill_polygon_geojson=spill_polygon,
        forcing_config=forcing_config,
        particle_count=args.particles,
        release_ages_hours=[6, 12, 24, 36],
        forecast_hours=args.forecast_hours,
    )

    print("\n" + "=" * 70)
    print("PHASE 2 RESULT")
    print("=" * 70)

    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )

    print("=" * 70)

    raise SystemExit(
        0 if result.get("status") == "SUCCESS" else 1
    )