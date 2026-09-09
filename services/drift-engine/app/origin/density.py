"""
Origin density calculation from hindcast trajectories.

Aggregates particle trajectories to create probability density fields.
"""

import logging
from typing import Optional

import numpy as np
import xarray as xr
from scipy.ndimage import gaussian_filter

from app.hindcast.models import HindcastResult

logger = logging.getLogger(__name__)


def calculate_origin_density(
    hindcast_result: HindcastResult,
    grid_resolution_km: float = 1.0,
    sigma_km: float = 2.0,
) -> Optional[xr.Dataset]:
    """
    Calculate origin density from hindcast results.

    Creates a regular grid and aggregates particle positions
    from backward simulations.

    Args:
        hindcast_result:
            HindcastResult from backward ensemble.

        grid_resolution_km:
            Grid resolution in kilometers.

        sigma_km:
            Gaussian filter sigma in kilometers.

    Returns:
        xarray Dataset with density grid,
        or None if no valid results.
    """

    logger.info(
        f"Calculating origin density with "
        f"{grid_resolution_km}km resolution"
    )

    # =========================================================
    # Collect final positions from all successful hindcasts
    # =========================================================

    all_lats = []
    all_lons = []

    for release_age in hindcast_result.release_ages:

        if release_age.simulation_result is None:
            continue

        final_lats, final_lons = (
            release_age.simulation_result.get_final_positions()
        )

        all_lats.extend(final_lats)
        all_lons.extend(final_lons)

    if len(all_lats) == 0:
        logger.warning(
            "No valid positions for origin density"
        )
        return None

    all_lats = np.asarray(all_lats)
    all_lons = np.asarray(all_lons)

    # =========================================================
    # Remove invalid particle positions
    # =========================================================

    valid_mask = ~(
        np.isnan(all_lats)
        | np.isnan(all_lons)
    )

    all_lats = all_lats[valid_mask]
    all_lons = all_lons[valid_mask]

    if len(all_lats) == 0:
        logger.warning(
            "No valid positions after NaN filtering"
        )
        return None

    logger.info(
        f"Aggregating {len(all_lats)} particles "
        f"into density grid"
    )

    # =========================================================
    # Calculate spatial bounds
    # =========================================================

    lat_min = np.nanmin(all_lats)
    lat_max = np.nanmax(all_lats)

    lon_min = np.nanmin(all_lons)
    lon_max = np.nanmax(all_lons)

    # =========================================================
    # Convert grid resolution from km to degrees
    # =========================================================

    lat_step_deg = (
        grid_resolution_km / 111.0
    )

    mean_lat = (
        lat_min + lat_max
    ) / 2.0

    cos_lat = np.cos(
        np.radians(mean_lat)
    )

    # Protect against division by zero near poles.
    cos_lat = max(abs(cos_lat), 1e-6)

    lon_step_deg = (
        grid_resolution_km
        / (111.0 * cos_lat)
    )

    # =========================================================
    # Add one-cell padding around data
    # =========================================================

    lat_pad = lat_step_deg
    lon_pad = lon_step_deg

    lat_start = lat_min - lat_pad
    lat_end = lat_max + lat_pad

    lon_start = lon_min - lon_pad
    lon_end = lon_max + lon_pad

    # =========================================================
    # Create histogram edges
    # =========================================================

    lat_edges = np.arange(
        lat_start,
        lat_end + lat_step_deg,
        lat_step_deg,
    )

    lon_edges = np.arange(
        lon_start,
        lon_end + lon_step_deg,
        lon_step_deg,
    )

    logger.info(
        f"Grid shape: "
        f"{len(lat_edges)}×{len(lon_edges)}"
    )

    # =========================================================
    # Histogram particles
    #
    # np.histogram2d returns:
    #   shape = (longitude_bins, latitude_bins)
    #
    # We transpose it to:
    #   (latitude_bins, longitude_bins)
    # =========================================================

    hist, lon_edges, lat_edges = np.histogram2d(
        all_lons,
        all_lats,
        bins=[
            lon_edges,
            lat_edges,
        ],
    )

    hist = hist.T

    logger.info(
        f"hist.shape after transpose: "
        f"{hist.shape}"
    )

    # =========================================================
    # Convert edges to grid centers
    # =========================================================

    lat_centers = (
        lat_edges[:-1]
        + lat_edges[1:]
    ) / 2.0

    lon_centers = (
        lon_edges[:-1]
        + lon_edges[1:]
    ) / 2.0

    logger.info(
        f"lat_centers.shape: "
        f"{lat_centers.shape}, "
        f"lon_centers.shape: "
        f"{lon_centers.shape}"
    )

    # =========================================================
    # Gaussian smoothing
    # =========================================================

    sigma_grid = (
        sigma_km
        / grid_resolution_km
    )

    hist_smooth = gaussian_filter(
        hist,
        sigma=sigma_grid,
    )

    logger.info(
        f"hist_smooth.shape: "
        f"{hist_smooth.shape}"
    )

    # =========================================================
    # Normalize density
    # =========================================================

    hist_norm = (
        hist_smooth
        / (hist_smooth.sum() + 1e-10)
    )

    # =========================================================
    # Create xarray Dataset
    # =========================================================

    logger.info(
        f"Creating xarray with data shape "
        f"{hist_smooth.shape}, "
        f"lat {len(lat_centers)}, "
        f"lon {len(lon_centers)}"
    )

    ds = xr.Dataset(
        {
            "density": (
                ["latitude", "longitude"],
                hist_smooth,
            ),
            "density_normalized": (
                ["latitude", "longitude"],
                hist_norm,
            ),
        },
        coords={
            "latitude": (
                "latitude",
                lat_centers,
            ),
            "longitude": (
                "longitude",
                lon_centers,
            ),
        },
    )

    ds.attrs[
        "long_name"
    ] = "Origin density from backward ensemble"

    ds.attrs[
        "units"
    ] = "particles per grid cell (normalized)"

    ds.attrs[
        "grid_resolution_km"
    ] = grid_resolution_km

    ds.attrs[
        "gaussian_sigma_km"
    ] = sigma_km

    logger.info(
        "Origin density calculated successfully"
    )

    return ds


def get_density_bounds(
    ds: xr.Dataset,
    level: float = 0.9,
) -> tuple[float, float, float, float]:
    """
    Get bounding box containing specified density level.

    Args:
        ds:
            xarray Dataset from calculate_origin_density.

        level:
            Cumulative density level (0-1).

    Returns:
        (lat_min, lat_max, lon_min, lon_max)
    """

    density = ds[
        "density_normalized"
    ].values

    # =========================================================
    # Find density threshold
    # =========================================================

    sorted_density = np.sort(
        density.flatten()
    )[::-1]

    cumsum = np.cumsum(
        sorted_density
    )

    cumsum_norm = (
        cumsum
        / cumsum[-1]
    )

    threshold_idx = np.argmax(
        cumsum_norm >= level
    )

    threshold = sorted_density[
        threshold_idx
    ]

    # =========================================================
    # Find cells above threshold
    # =========================================================

    mask = density >= threshold

    lats = ds.latitude.values
    lons = ds.longitude.values

    lat_indices, lon_indices = np.where(
        mask
    )

    if len(lat_indices) == 0:
        logger.warning(
            f"No cells at density level {level}"
        )

        return 0, 0, 0, 0

    lat_min = lats[
        lat_indices
    ].min()

    lat_max = lats[
        lat_indices
    ].max()

    lon_min = lons[
        lon_indices
    ].min()

    lon_max = lons[
        lon_indices
    ].max()

    return (
        lat_min,
        lat_max,
        lon_min,
        lon_max,
    )