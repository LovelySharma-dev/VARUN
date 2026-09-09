"""Write artifacts to disk."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import geopandas as gpd
import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)


def write_netcdf_dataset(
    ds: xr.Dataset,
    output_path: Path,
    compress: bool = True,
) -> Path:
    """
    Write xarray Dataset to NetCDF.

    Args:
        ds: xarray Dataset
        output_path: Output file path
        compress: Enable compression

    Returns:
        Path to written file
    """
    logger.info(f"Writing NetCDF to {output_path.name}")

    encoding = {}
    if compress:
        for var in ds.data_vars:
            encoding[var] = {"zlib": True, "complevel": 4}

    ds.to_netcdf(output_path, encoding=encoding)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"NetCDF written ({size_mb:.2f} MB)")

    return output_path


def write_geodataframe_geojson(
    gdf: gpd.GeoDataFrame,
    output_path: Path,
) -> Path:
    """
    Write GeoDataFrame to GeoJSON.

    Args:
        gdf: GeoPandas GeoDataFrame
        output_path: Output file path

    Returns:
        Path to written file
    """
    logger.info(f"Writing GeoJSON to {output_path.name}")

    gdf.to_file(output_path, driver="GeoJSON")
    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"GeoJSON written ({size_mb:.2f} MB)")

    return output_path


def write_json_manifest(
    manifest: dict,
    output_path: Path,
) -> Path:
    """
    Write JSON manifest.

    Args:
        manifest: Dictionary to write
        output_path: Output file path

    Returns:
        Path to written file
    """
    logger.info(f"Writing JSON manifest to {output_path.name}")

    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    logger.info(f"JSON manifest written")
    return output_path


def create_trajectory_geojson(
    trajectory_lats: np.ndarray,
    trajectory_lons: np.ndarray,
    trajectory_times: list[datetime],
    particle_indices: Optional[list[int]] = None,
) -> dict:
    """
    Create GeoJSON FeatureCollection from trajectory.

    Args:
        trajectory_lats: (n_times, n_particles)
        trajectory_lons: (n_times, n_particles)
        trajectory_times: List of datetime objects
        particle_indices: Specific particles to include (None = all)

    Returns:
        GeoJSON FeatureCollection dict
    """
    n_times, n_particles = trajectory_lats.shape

    if particle_indices is None:
        particle_indices = list(range(n_particles))

    features = []

    for pid in particle_indices:
        coords = []
        for t in range(n_times):
            lon = float(trajectory_lons[t, pid])
            lat = float(trajectory_lats[t, pid])

            # Skip invalid coordinates
            if not (np.isnan(lon) or np.isnan(lat)):
                coords.append([lon, lat])

        if len(coords) > 1:
            feature = {
                "type": "Feature",
                "properties": {
                    "particle_id": int(pid),
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords,
                },
            }
            features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def create_particle_positions_geojson(
    lats: np.ndarray,
    lons: np.ndarray,
    properties: Optional[dict] = None,
) -> dict:
    """
    Create GeoJSON FeatureCollection from particle positions.

    Args:
        lats: Particle latitudes
        lons: Particle longitudes
        properties: Common properties for all particles

    Returns:
        GeoJSON FeatureCollection dict
    """
    features = []
    props = properties or {}

    for i, (lat, lon) in enumerate(zip(lats, lons)):
        if np.isnan(lat) or np.isnan(lon):
            continue

        feature = {
            "type": "Feature",
            "properties": {
                "particle_id": int(i),
                **props,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [float(lon), float(lat)],
            },
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
    }