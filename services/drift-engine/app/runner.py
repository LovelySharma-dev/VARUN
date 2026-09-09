"""Main Phase 2 orchestrator runner."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import xarray as xr

from app.artifacts import (
    create_particle_positions_geojson,
    write_geodataframe_geojson,
    write_json_manifest,
    write_netcdf_dataset,
)
from app.config import Phase2Settings
from app.contracts import Centroid, Observation, OriginRegion, Phase2ArtifactManifest, Phase2SearchWindow, SearchWindow
from app.exceptions import Phase2Error
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


class Phase2Runner:
    """Main orchestrator for Phase 2 workflow."""

    def __init__(self, settings: Optional[Phase2Settings] = None):
        """Initialize Phase 2 runner."""
        self.settings = settings or Phase2Settings()
        self.engine = DriftSimulationEngine()

    def run_phase2(
        self,
        case_id: str,
        scene_id: Optional[str],
        observation_time: datetime,
        spill_polygon_geojson: dict,
        forcing_config: ForcingConfig,
        particle_count: int = 1500,
        release_ages_hours: Optional[list[int]] = None,
        forecast_hours: float = 24.0,
    ) -> dict:
        """
        Run complete Phase 2 workflow.

        Args:
            case_id: Case identifier
            scene_id: SAR scene identifier
            observation_time: Time of observation
            spill_polygon_geojson: GeoJSON polygon of spill
            forcing_config: Forcing file configuration
            particle_count: Number of particles
            release_ages_hours: Release age candidates (hours)
            forecast_hours: Forecast duration (hours)

        Returns:
            Dictionary with run metadata and artifact paths
        """
        run_id = generate_run_id()
        run_dir = ensure_output_dir(self.settings.output_dir, run_id)

        logger.info(f"\n{'='*60}")
        logger.info(f"VARUN Phase 2 Simulation")
        logger.info(f"{'='*60}")
        logger.info(f"Run ID: {run_id}")
        logger.info(f"Case ID: {case_id}")
        logger.info(f"Observation: {observation_time.isoformat()}")
        logger.info(f"Output dir: {run_dir}")

        observation_time = normalize_simulation_time(observation_time, "observation_time")
        release_ages_hours = release_ages_hours or self.settings.release_ages_hours

        try:
            # ========== STEP 1: Audit forcing ==========
            logger.info("\n[STEP 1] Auditing forcing files...")

            forcing_files = forcing_config.get_files()
            forcing_audits = {}
            for file_path in forcing_files:
                audit_result = audit_forcing_file(file_path)
                forcing_audits[file_path.name] = audit_result
                if not audit_result.passed:
                    raise Phase2Error(
                        f"Forcing validation failed for {file_path.name}: {audit_result.errors}"
                    )
                logger.info(f"✓ {file_path.name} passed audit")

            # Save audit results
            audit_path = run_dir / "forcing-audit.json"
            audit_dict = {
                name: {
                    "passed": result.passed,
                    "errors": result.errors,
                    "warnings": result.warnings,
                }
                for name, result in forcing_audits.items()
            }
            write_json_manifest(audit_dict, audit_path)

            # ========== STEP 2: Create readers ==========
            logger.info("\n[STEP 2] Creating OpenDrift readers...")
            readers = create_combined_readers(
                current_file=forcing_config.current_file,
                wind_file=forcing_config.wind_file,
                combined_file=forcing_config.combined_file,
            )
            logger.info(f"✓ Created {len(readers)} reader(s)")

            # ========== STEP 3: Run hindcast ==========
            logger.info("\n[STEP 3] Running backward ensemble...")
            seeding_config = SeedingConfig(
                particle_count=particle_count,
                seed_buffer_km=self.settings.seed_buffer_km,
                random_seed=self.settings.random_seed,
            )

            hindcast_runner = HindcastRunner(self.engine)
            hindcast_result = hindcast_runner.run_hindcast(
                run_id=run_id,
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
            logger.info(f"✓ Hindcast complete: {len(successful_ages)}/{len(release_ages_hours)} ages")

            # Save hindcast results
            hindcast_dir = run_dir / "backward"
            hindcast_dir.mkdir(exist_ok=True)

            for ra in successful_ages:
                try:
                    simulation_result = ra.simulation_result
                    if simulation_result is None:
                        continue
                    output_file = hindcast_dir / f"release-{ra.release_age_hours}h.nc"
                    ds = xr.Dataset(
                        {
                            "lon": (["time", "trajectory"], simulation_result.trajectory_lons),
                            "lat": (["time", "trajectory"], simulation_result.trajectory_lats),
                        },
                        coords={
                            "time": [t.isoformat() for t in simulation_result.trajectory_times],
                        },
                    )
                    write_netcdf_dataset(ds, output_file)
                except Exception as e:
                    logger.warning(f"Could not save hindcast {ra.release_age_hours}h: {e}")

            # ========== STEP 4: Calculate origin density ==========
            logger.info("\n[STEP 4] Calculating origin density...")

            density_ds = calculate_origin_density(
                hindcast_result,
                grid_resolution_km=self.settings.density_grid_resolution_km,
            )

            if density_ds is not None:
                density_file = run_dir / "origin" / "density.nc"
                density_file.parent.mkdir(exist_ok=True)
                write_netcdf_dataset(density_ds, density_file)
                logger.info("✓ Origin density calculated")

                # Generate contours
                contours_gdf = generate_contours(
                    density_ds,
                    levels=self.settings.contour_levels,
                )
                if contours_gdf is not None:
                    contours_file = run_dir / "origin" / "contours.geojson"
                    write_geodataframe_geojson(contours_gdf, contours_file)
                    logger.info("✓ Contours generated")
            else:
                logger.warning("Could not calculate origin density")
                density_file = None

            # ========== STEP 5: Rank release ages ==========
            logger.info("\n[STEP 5] Ranking release ages...")

            for i, ra in enumerate(successful_ages, 1):
                ra.rank = i
                ra.ranking_score = 1.0 / i

            best_ra = hindcast_result.best_release_age
            if best_ra:
                logger.info(f"✓ Best release age: {best_ra.release_age_hours}h (rank {best_ra.rank})")
            else:
                logger.warning("Could not determine best release age")
                return {"status": "FAILED", "errors": ["No valid hindcasts"]}

            # ========== STEP 6: Run reconstruction ==========
            logger.info("\n[STEP 6] Running forward reconstruction...")

            # Get centroid of origin density for reconstruction start point
            if density_ds is not None:
                lat_min, lat_max, lon_min, lon_max = get_density_bounds(
                    density_ds, level=0.9
                )
                best_origin_lat = (lat_min + lat_max) / 2
                best_origin_lon = (lon_min + lon_max) / 2
            else:
                # Fallback to spill centroid
                from shapely.geometry import shape
                poly = shape(spill_polygon_geojson)
                best_origin_lon, best_origin_lat = poly.centroid.coords[0]

            reconstruction_runner = ReconstructionRunner(self.engine)
            reconstruction = reconstruction_runner.run(
                run_id=run_id,
                best_origin_lat=best_origin_lat,
                best_origin_lon=best_origin_lon,
                observation_time=observation_time,
                release_age_hours=best_ra.release_age_hours,
                readers=readers,
                seeding_config=seeding_config,
            )

            if reconstruction:
                logger.info("✓ Reconstruction complete")
                recon_file = run_dir / "reconstruction" / "trajectory.nc"
                recon_file.parent.mkdir(exist_ok=True)
                ds_recon = xr.Dataset(
                    {
                        "lon": (["time", "trajectory"], reconstruction.simulation_result.trajectory_lons),
                        "lat": (["time", "trajectory"], reconstruction.simulation_result.trajectory_lats),
                    },
                )
                write_netcdf_dataset(ds_recon, recon_file)
            else:
                logger.warning("Reconstruction failed")
                reconstruction = None

            # ========== STEP 7: Run forecast ==========
            logger.info("\n[STEP 7] Running future forecast...")

            forecast_result = None
            if reconstruction:
                forecast_runner = ForecastRunner(self.engine)
                forecast_result = forecast_runner.run_forecast(
                    run_id=run_id,
                    reconstruction=reconstruction,
                    forecast_hours=forecast_hours,
                    readers=readers,
                )

                if forecast_result:
                    logger.info("✓ Forecast complete")
                    forecast_file = run_dir / "forecast" / "forecast.nc"
                    forecast_file.parent.mkdir(exist_ok=True)
                    ds_forecast = xr.Dataset(
                        {
                            "lon": (["time", "trajectory"], forecast_result.trajectory_lons),
                            "lat": (["time", "trajectory"], forecast_result.trajectory_lats),
                        },
                    )
                    write_netcdf_dataset(ds_forecast, forecast_file)
                    
                    # Also create GeoJSON
                    final_lats, final_lons = forecast_result.get_final_positions()
                    forecast_geojson = create_particle_positions_geojson(final_lats, final_lons)
                    forecast_geojson_file = run_dir / "forecast" / "forecast.geojson"
                    with open(forecast_geojson_file, "w") as f:
                        json.dump(forecast_geojson, f)
                else:
                    logger.warning("Forecast failed")

            # ========== STEP 8: Generate Phase 3 search window ==========
            logger.info("\n[STEP 8] Generating Phase 3 search window...")

            if density_ds is not None:
                lat_min, lat_max, lon_min, lon_max = get_density_bounds(
                    density_ds, level=0.9
                )
            else:
                from shapely.geometry import shape
                poly = shape(spill_polygon_geojson)
                bounds = poly.bounds  # (minx, miny, maxx, maxy)
                lon_min, lat_min, lon_max, lat_max = bounds

            search_window = SearchWindow(
                min_lat=lat_min,
                max_lat=lat_max,
                min_lon=lon_min,
                max_lon=lon_max,
                start_time=observation_time,
                end_time=observation_time,
            )

            phase3_contract = Phase2SearchWindow(
                case_id=case_id,
                scene_id=scene_id,
                generated_at=datetime.utcnow(),
                observation=Observation(acquired_at=observation_time),
                best_release_age_hours=best_ra.release_age_hours,
                origin=OriginRegion(
                    centroid=Centroid(lon=best_origin_lon, lat=best_origin_lat),
                    radius_km=self.settings.seed_buffer_km,
                ),
                search_window=search_window,
                forecast=None,
                artifacts=[],
                random_seed=self.settings.random_seed,
                phase2_run_id=run_id,
            )

            contract_file = run_dir / "phase2-search-window.json"
            with open(contract_file, "w") as f:
                json.dump(phase3_contract.dict(), f, indent=2, default=str)
            logger.info("✓ Phase 3 search window generated")

            # ========== STEP 9: Generate manifest ==========
            logger.info("\n[STEP 9] Generating artifact manifest...")

            artifacts = []
            for file in run_dir.rglob("*"):
                if file.is_file():
                    artifacts.append(str(file.relative_to(run_dir)))

            manifest = Phase2ArtifactManifest(
                run_id=run_id,
                case_id=case_id,
                status="SUCCESS",
                created_at=datetime.utcnow(),
                artifacts=[{"path": a} for a in sorted(artifacts)],
            )

            manifest_file = run_dir / "manifest.json"
            with open(manifest_file, "w") as f:
                json.dump(manifest.dict(), f, indent=2, default=str)
            logger.info("✓ Manifest generated")

            logger.info(f"\n{'='*60}")
            logger.info(f"✓ Phase 2 COMPLETE")
            logger.info(f"{'='*60}\n")

            return {
                "status": "SUCCESS",
                "run_id": run_id,
                "case_id": case_id,
                "output_dir": str(run_dir),
                "artifacts": artifacts,
            }

        except Exception as e:
            logger.error(f"\n✗ Phase 2 FAILED: {e}", exc_info=True)
            return {
                "status": "FAILED",
                "run_id": run_id,
                "error": str(e),
            }


def cli_main():
    """CLI entry point."""
    import sys
    import click

    @click.command()
    @click.option("--case-id", required=True)
    @click.option("--observation-time", required=True, help="ISO-8601 datetime")
    @click.option("--polygon-file", required=True, type=click.Path(exists=True))
    @click.option("--current-file", type=click.Path(exists=True))
    @click.option("--wind-file", type=click.Path(exists=True))
    @click.option("--particles", default=1500, type=int)
    def run(case_id, observation_time, polygon_file, current_file, wind_file, particles):
        """Run Phase 2 simulation."""
        with open(polygon_file) as f:
            polygon = json.load(f)

        forcing_config = ForcingConfig(
            current_file=Path(current_file) if current_file else None,
            wind_file=Path(wind_file) if wind_file else None,
        )

        runner = Phase2Runner()
        result = runner.run_phase2(
            case_id=case_id,
            scene_id=None,
            observation_time=datetime.fromisoformat(observation_time),
            spill_polygon_geojson=polygon,
            forcing_config=forcing_config,
            particle_count=particles,
        )

        print(json.dumps(result, indent=2, default=str))
        sys.exit(0 if result["status"] == "SUCCESS" else 1)

    run()


if __name__ == "__main__":
    cli_main()