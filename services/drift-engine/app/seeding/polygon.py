"""
Polygon-based particle seeding for oil spills.

Seeds particles within or around a spill polygon.
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import unary_union

from app.exceptions import InvalidSpillGeometryError, SeedingError
from app.seeding.models import SeedingConfig, SeedingResult
from app.utils import haversine_distance, normalize_simulation_time

logger = logging.getLogger(__name__)


def seed_from_polygon(
    polygon_geojson: dict,
    seeding_time: datetime,
    config: SeedingConfig,
) -> SeedingResult:
    """
    Seed particles within a spill polygon.

    Args:
        polygon_geojson: GeoJSON polygon dict
        seeding_time: Time at which particles are seeded
        config: Seeding configuration

    Returns:
        SeedingResult with particle positions

    Raises:
        InvalidSpillGeometryError: If polygon is invalid
        SeedingError: If seeding fails
    """
    try:
        # Parse GeoJSON
        if polygon_geojson.get("type") != "Polygon":
            raise ValueError("Input must be a Polygon")

        poly = shape(polygon_geojson)

        if not poly.is_valid:
            raise ValueError(f"Invalid polygon: {poly.is_valid}")

        if poly.is_empty:
            raise ValueError("Polygon is empty")

        logger.info(
            f"Seeding {config.particle_count} particles in polygon "
            f"with area {poly.area:.2e} degrees²"
        )

    except Exception as e:
        raise InvalidSpillGeometryError(
            f"Invalid spill polygon: {e}",
            details={"polygon_type": polygon_geojson.get("type")},
        ) from e

    # Create buffered polygon if needed
    if config.seed_buffer_km > 0:
        buffer_degrees = _km_to_degrees(config.seed_buffer_km, poly.centroid.y)
        poly_buffered = poly.buffer(buffer_degrees)
        logger.info(f"Added {config.seed_buffer_km} km buffer to polygon")
    else:
        poly_buffered = poly

    # Seed particles
    try:
        if config.random_seed is not None:
            np.random.seed(config.random_seed)

        lats, lons = _seed_polygon(poly_buffered, config.particle_count)

        logger.info(
            f"Seeded {len(lats)} particles "
            f"in lat [{lats.min():.3f}, {lats.max():.3f}] "
            f"lon [{lons.min():.3f}, {lons.max():.3f}]"
        )

    except Exception as e:
        raise SeedingError(f"Particle seeding failed: {e}") from e

    seeding_time_norm = normalize_simulation_time(seeding_time, "seeding_time")

    return SeedingResult(
        particle_count=config.particle_count,
        effective_particle_count=len(lats),
        particles_on_land_count=config.particle_count - len(lats),
        initial_positions={"lats": lats.tolist(), "lons": lons.tolist()},
        seeding_time=seeding_time_norm,
        seed_geom_wkt=poly_buffered.wkt,
    )


def _seed_polygon(
    poly: Polygon,
    n_particles: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Seed particles uniformly within polygon.

    Args:
        poly: Shapely Polygon
        n_particles: Number of particles to generate

    Returns:
        (lats, lons) arrays
    """
    # Get bounding box
    minx, miny, maxx, maxy = poly.bounds

    lats = []
    lons = []

    # Rejection sampling until we have enough particles
    attempts = 0
    max_attempts = n_particles * 10

    while len(lats) < n_particles and attempts < max_attempts:
        # Generate random points in bounding box
        n_gen = n_particles - len(lats)
        random_lons = np.random.uniform(minx, maxx, n_gen)
        random_lats = np.random.uniform(miny, maxy, n_gen)

        # Check which are inside polygon
        for lon, lat in zip(random_lons, random_lats):
            point = Polygon([(lon, lat), (lon, lat), (lon, lat)])  # Degenerate polygon as point
            from shapely.geometry import Point
            point = Point(lon, lat)
            if poly.contains(point) or poly.touches(point):
                lats.append(lat)
                lons.append(lon)

        attempts += n_gen

    if len(lats) < n_particles:
        logger.warning(
            f"Could only seed {len(lats)} particles out of {n_particles} requested "
            f"in {attempts} attempts"
        )

    return np.array(lats), np.array(lons)


def _km_to_degrees(km: float, latitude: float) -> float:
    """
    Convert kilometers to degrees at given latitude.

    Uses simplified approximation.
    """
    # At the equator, 1 degree latitude ≈ 111 km
    # For longitude, it depends on latitude: 1 degree lon ≈ 111 * cos(lat) km
    lat_rad = np.radians(latitude)

    # Use latitude distance as approximation
    degrees = km / 111.0
    return degrees


def seed_from_point(
    centroid_lat: float,
    centroid_lon: float,
    radius_km: float,
    seeding_time: datetime,
    config: SeedingConfig,
) -> SeedingResult:
    """
    Seed particles around a point (create circular polygon).

    Args:
        centroid_lat: Latitude of center
        centroid_lon: Longitude of center
        radius_km: Radius in kilometers
        seeding_time: Time at which particles are seeded
        config: Seeding configuration

    Returns:
        SeedingResult with particle positions
    """
    from shapely.geometry import Point

    # Create circular polygon
    center = Point(centroid_lon, centroid_lat)
    buffer_degrees = _km_to_degrees(radius_km, centroid_lat)
    circle_poly = center.buffer(buffer_degrees)

    # Convert to GeoJSON and use polygon seeding
    circle_geojson = mapping(circle_poly)

    return seed_from_polygon(circle_geojson, seeding_time, config)