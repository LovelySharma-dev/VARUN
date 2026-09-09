"""Generate contours from origin density."""

import logging
from typing import Optional

import geopandas as gpd
import numpy as np
import xarray as xr
from shapely.geometry import Polygon
from skimage.measure import find_contours

logger = logging.getLogger(__name__)


def generate_contours(
    density_ds: xr.Dataset,
    levels: list[float] = [0.5, 0.75, 0.9],
    release_age_hours: Optional[int] = None,
) -> Optional[gpd.GeoDataFrame]:
    """
    Generate contours from origin density.

    Args:
        density_ds: xarray Dataset from calculate_origin_density
        levels: Contour probability levels
        release_age_hours: Release age for metadata

    Returns:
        GeoDataFrame with contour features, or None if generation fails
    """
    logger.info(f"Generating contours at levels {levels}")

    density = density_ds["density_normalized"].values
    lats = density_ds.latitude.values
    lon = density_ds.longitude.values

    features = []

    for level in levels:
        logger.info(f"Extracting contour at level {level}")

        # Find threshold value for this level
        sorted_density = np.sort(density.flatten())[::-1]
        cumsum = np.cumsum(sorted_density)
        cumsum_norm = cumsum / (cumsum[-1] + 1e-10)

        threshold_idx = np.searchsorted(cumsum_norm[::-1], level)
        if threshold_idx < len(sorted_density):
            threshold = sorted_density[threshold_idx]
        else:
            logger.warning(f"Cannot find density level {level}")
            continue

        # Find contours
        contours = find_contours(density, threshold)

        for contour in contours:
            if len(contour) < 3:
                continue

            # Convert contour indices to lat/lon
            contour_coords = []
            for idx in contour:
                lat_idx = int(idx[0])
                lon_idx = int(idx[1])

                if 0 <= lat_idx < len(lats) and 0 <= lon_idx < len(lon):
                    lat = lats[lat_idx]
                    lon_val = lon[lon_idx]
                    contour_coords.append((lon_val, lat))

            if len(contour_coords) >= 3:
                try:
                    poly = Polygon(contour_coords)
                    if poly.is_valid:
                        features.append(
                            {
                                "geometry": poly,
                                "level": level,
                                "releaseAgeHours": release_age_hours,
                            }
                        )
                except Exception as e:
                    logger.debug(f"Skipped invalid contour: {e}")

    if not features:
        logger.warning("No valid contours generated")
        return None

    gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")
    logger.info(f"Generated {len(gdf)} contour features")

    return gdf