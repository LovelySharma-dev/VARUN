"""
Polygon-based particle seeding for oil spills.

Supports:
- GeoJSON Polygon
- GeoJSON MultiPolygon
- GeoJSON Feature
- GeoJSON FeatureCollection

All coordinates are assumed to be EPSG:4326 lon/lat.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

import numpy as np
from shapely.geometry import (
    MultiPolygon,
    Point,
    Polygon,
    mapping,
    shape,
)
from shapely.ops import unary_union

from app.exceptions import InvalidSpillGeometryError, SeedingError
from app.seeding.models import SeedingConfig, SeedingResult
from app.utils import normalize_simulation_time


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------


def seed_from_polygon(
    polygon_geojson: dict,
    seeding_time: datetime,
    config: SeedingConfig,
) -> SeedingResult:
    """
    Seed particles within or around a Polygon/MultiPolygon.

    Supported input structures:

    1. Geometry:
        {
            "type": "Polygon",
            "coordinates": [...]
        }

    2. Geometry:
        {
            "type": "MultiPolygon",
            "coordinates": [...]
        }

    3. Feature:
        {
            "type": "Feature",
            "geometry": {
                "type": "MultiPolygon",
                ...
            },
            "properties": {...}
        }

    4. FeatureCollection:
        {
            "type": "FeatureCollection",
            "features": [...]
        }

    Coordinates:
        EPSG:4326 longitude/latitude.

    Returns:
        SeedingResult
    """

    try:
        # ---------------------------------------------------------------
        # Validate basic input
        # ---------------------------------------------------------------

        if not isinstance(polygon_geojson, dict):
            raise ValueError(
                "polygon_geojson must be a dictionary"
            )

        # ---------------------------------------------------------------
        # Extract actual geometry
        # ---------------------------------------------------------------

        geometry_geojson = _extract_geometry(polygon_geojson)

        geometry_type = geometry_geojson.get("type")

        if geometry_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError(
                "Input geometry must be Polygon or MultiPolygon, "
                f"got {geometry_type}"
            )

        # ---------------------------------------------------------------
        # Convert GeoJSON -> Shapely geometry
        # ---------------------------------------------------------------

        poly = shape(geometry_geojson)

        if poly.is_empty:
            raise ValueError(
                "Spill geometry is empty"
            )

        # ---------------------------------------------------------------
        # Validate / repair geometry
        # ---------------------------------------------------------------

        if not poly.is_valid:
            logger.warning(
                "Spill geometry is invalid. "
                "Applying make_valid/buffer(0)."
            )

            try:
                from shapely.validation import make_valid

                poly = make_valid(poly)

            except ImportError:
                poly = poly.buffer(0)

        if poly.is_empty:
            raise ValueError(
                "Spill geometry became empty after validation"
            )

        # ---------------------------------------------------------------
        # Normalize geometry type
        # ---------------------------------------------------------------

        if poly.geom_type not in {
            "Polygon",
            "MultiPolygon",
        }:
            raise ValueError(
                "Unexpected normalized geometry type: "
                f"{poly.geom_type}"
            )

        # ---------------------------------------------------------------
        # If make_valid produced GeometryCollection,
        # extract Polygon/MultiPolygon components.
        # ---------------------------------------------------------------

        if poly.geom_type == "GeometryCollection":
            polygon_parts = [
                geom
                for geom in poly.geoms
                if geom.geom_type in {
                    "Polygon",
                    "MultiPolygon",
                }
            ]

            if not polygon_parts:
                raise ValueError(
                    "Geometry validation produced no polygon geometry"
                )

            poly = unary_union(polygon_parts)

        # ---------------------------------------------------------------
        # Final geometry type validation
        # ---------------------------------------------------------------

        if poly.geom_type not in {
            "Polygon",
            "MultiPolygon",
        }:
            raise ValueError(
                "Unsupported geometry after normalization: "
                f"{poly.geom_type}"
            )

        # ---------------------------------------------------------------
        # Log geometry information
        # ---------------------------------------------------------------

        logger.info(
            "Spill geometry: type=%s bounds=%s "
            "centroid=(%.8f, %.8f)",
            poly.geom_type,
            poly.bounds,
            poly.centroid.x,
            poly.centroid.y,
        )

        # ---------------------------------------------------------------
        # EPSG:4326 bounds validation
        #
        # bounds = min_lon, min_lat, max_lon, max_lat
        # ---------------------------------------------------------------

        min_lon, min_lat, max_lon, max_lat = poly.bounds

        if not (
            -180.0 <= min_lon <= 180.0
            and -180.0 <= max_lon <= 180.0
            and -90.0 <= min_lat <= 90.0
            and -90.0 <= max_lat <= 90.0
        ):
            raise ValueError(
                "Geometry coordinates are outside valid "
                f"EPSG:4326 bounds: {poly.bounds}"
            )

        # ---------------------------------------------------------------
        # Validate particle count
        # ---------------------------------------------------------------

        if config.particle_count <= 0:
            raise ValueError(
                "particle_count must be greater than zero"
            )

        # ---------------------------------------------------------------
        # Validate seed buffer
        # ---------------------------------------------------------------

        if config.seed_buffer_km < 0:
            raise ValueError(
                "seed_buffer_km must be >= 0"
            )

        # ---------------------------------------------------------------
        # Apply seed buffer
        #
        # NOTE:
        # This uses the existing approximate km->degree conversion.
        # ---------------------------------------------------------------

        if config.seed_buffer_km > 0:

            buffer_degrees = _km_to_degrees(
                config.seed_buffer_km,
                poly.centroid.y,
            )

            poly_buffered = poly.buffer(
                buffer_degrees
            )

            logger.info(
                "Added %.3f km seed buffer "
                "(%.8f degrees)",
                config.seed_buffer_km,
                buffer_degrees,
            )

        else:
            poly_buffered = poly

        # ---------------------------------------------------------------
        # Validate buffered geometry
        # ---------------------------------------------------------------

        if poly_buffered.is_empty:
            raise SeedingError(
                "Seed geometry became empty after buffering"
            )

        if not poly_buffered.is_valid:
            logger.warning(
                "Buffered seed geometry is invalid. "
                "Applying buffer(0)."
            )

            poly_buffered = poly_buffered.buffer(0)

        # ---------------------------------------------------------------
        # Deterministic random seed
        # ---------------------------------------------------------------

        if config.random_seed is not None:
            random_seed = int(config.random_seed)
        else:
            random_seed = None

        # ---------------------------------------------------------------
        # Seed particles
        # ---------------------------------------------------------------

        lats, lons = _seed_polygon(
            poly_buffered,
            config.particle_count,
            random_seed=random_seed,
        )

        # ---------------------------------------------------------------
        # Verify particle count
        # ---------------------------------------------------------------

        if len(lats) != config.particle_count:
            raise SeedingError(
                "Particle count mismatch: "
                f"requested={config.particle_count}, "
                f"generated={len(lats)}"
            )

        # ---------------------------------------------------------------
        # Validate generated particles
        # ---------------------------------------------------------------

        _validate_seeded_particles(
            lats=lats,
            lons=lons,
            polygon=poly_buffered,
        )

        # ---------------------------------------------------------------
        # Log ranges
        # ---------------------------------------------------------------

        logger.info(
            "Seeded %d particles",
            len(lats),
        )

        logger.info(
            "Seed longitude range: %.8f -> %.8f",
            float(lons.min()),
            float(lons.max()),
        )

        logger.info(
            "Seed latitude range: %.8f -> %.8f",
            float(lats.min()),
            float(lats.max()),
        )

    except InvalidSpillGeometryError:
        raise

    except Exception as exc:
        raise InvalidSpillGeometryError(
            f"Invalid spill polygon: {exc}",
            details={
                "polygon_type": (
                    polygon_geojson.get("type")
                    if isinstance(polygon_geojson, dict)
                    else None
                ),
            },
        ) from exc
    
    seeding_time_norm = normalize_simulation_time(
        seeding_time,
        "seeding_time",
    )

    return SeedingResult(
        particle_count=config.particle_count,
        effective_particle_count=len(lats),
        particles_on_land_count=(
            config.particle_count - len(lats)
        ),
        initial_positions={
            "lats": lats.tolist(),
            "lons": lons.tolist(),
        },
        seeding_time=seeding_time_norm,
        seed_geom_wkt=poly_buffered.wkt,
    )


def _extract_geometry(
    geojson: dict,
) -> dict:
    """
    Extract a Polygon/MultiPolygon geometry from:

    - Geometry
    - Feature
    - FeatureCollection

    Returns:
        GeoJSON geometry dictionary.
    """

    geojson_type = geojson.get("type")

    if geojson_type in {
        "Polygon",
        "MultiPolygon",
    }:
        return geojson

    if geojson_type == "Feature":

        geometry = geojson.get("geometry")

        if geometry is None:
            raise ValueError(
                "Feature does not contain geometry"
            )

        if geometry.get("type") not in {
            "Polygon",
            "MultiPolygon",
        }:
            raise ValueError(
                "Feature geometry must be Polygon or MultiPolygon, "
                f"got {geometry.get('type')}"
            )

        return geometry
    
    if geojson_type == "FeatureCollection":

        features = geojson.get("features")

        if not features:
            raise ValueError(
                "FeatureCollection contains no features"
            )

        polygon_geometries = []

        for index, feature in enumerate(features):

            if not isinstance(feature, dict):
                raise ValueError(
                    f"Feature at index {index} is invalid"
                )

            geometry = feature.get("geometry")

            if geometry is None:
                logger.warning(
                    "Feature %d has no geometry; skipping",
                    index,
                )
                continue

            geometry_type = geometry.get("type")

            if geometry_type not in {
                "Polygon",
                "MultiPolygon",
            }:
                logger.warning(
                    "Feature %d has unsupported geometry "
                    "type %s; skipping",
                    index,
                    geometry_type,
                )
                continue

            polygon_geometries.append(
                shape(geometry)
            )

        if not polygon_geometries:
            raise ValueError(
                "FeatureCollection contains no "
                "Polygon/MultiPolygon geometries"
            )

        merged = unary_union(
            polygon_geometries
        )

        return mapping(merged)

    raise ValueError(
        "Unsupported GeoJSON type: "
        f"{geojson_type}"
    )


def _seed_polygon(
    geometry: Polygon | MultiPolygon,
    n_particles: int,
    random_seed: Optional[int] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Seed particles uniformly inside Polygon or MultiPolygon.

    Uses rejection sampling inside the geometry bounding box.

    Args:
        geometry:
            Shapely Polygon or MultiPolygon.

        n_particles:
            Number of particles to generate.

        random_seed:
            Optional deterministic random seed.

    Returns:
        Tuple:
            latitudes: np.ndarray
            longitudes: np.ndarray
    """

    if not isinstance(
        geometry,
        (Polygon, MultiPolygon),
    ):
        raise SeedingError(
            "Unsupported geometry type: "
            f"{geometry.geom_type}. "
            "Expected Polygon or MultiPolygon."
        )

    if geometry.is_empty:
        raise SeedingError(
            "Cannot seed particles inside "
            "an empty geometry."
        )

    if n_particles <= 0:
        raise SeedingError(
            f"n_particles must be > 0, got {n_particles}"
        )

    minx, miny, maxx, maxy = geometry.bounds

    rng = np.random.default_rng(
        random_seed
    )

    lats: list[float] = []
    lons: list[float] = []

    batch_size = max(
        5000,
        n_particles * 10,
    )

    max_attempts = max(
        n_particles * 500,
        250000,
    )

    attempts = 0

    while (
        len(lats) < n_particles
        and attempts < max_attempts
    ):

        remaining = (
            n_particles - len(lats)
        )

        count = min(
            batch_size,
            max(
                remaining * 10,
                1000,
            ),
        )

        random_lons = rng.uniform(
            minx,
            maxx,
            count,
        )

        random_lats = rng.uniform(
            miny,
            maxy,
            count,
        )

        for lon, lat in zip(
            random_lons,
            random_lats,
        ):

            attempts += 1

            point = Point(
                float(lon),
                float(lat),
            )

            if geometry.covers(point):

                lons.append(
                    float(lon)
                )

                lats.append(
                    float(lat)
                )

                if len(lats) >= n_particles:
                    break

            if attempts >= max_attempts:
                break

    if len(lats) < n_particles:

        raise SeedingError(
            f"Could only seed {len(lats)} "
            f"particles out of {n_particles} "
            f"requested after {attempts} attempts"
        )

    return (
        np.asarray(
            lats,
            dtype=np.float64,
        ),
        np.asarray(
            lons,
            dtype=np.float64,
        ),
    )


def _validate_seeded_particles(
    lats: np.ndarray,
    lons: np.ndarray,
    polygon: Polygon | MultiPolygon,
) -> None:
    """
    Strong validation of generated particle coordinates.
    """

    if not isinstance(lats, np.ndarray):
        raise SeedingError(
            "Particle latitudes must be a NumPy array"
        )

    if not isinstance(lons, np.ndarray):
        raise SeedingError(
            "Particle longitudes must be a NumPy array"
        )

    if len(lats) != len(lons):
        raise SeedingError(
            "Latitude/longitude particle counts differ"
        )

    if len(lats) == 0:
        raise SeedingError(
            "Zero particles generated"
        )

    if not np.all(
        np.isfinite(lats)
    ):
        raise SeedingError(
            "Particle latitudes contain NaN/Inf"
        )

    if not np.all(
        np.isfinite(lons)
    ):
        raise SeedingError(
            "Particle longitudes contain NaN/Inf"
        )

    if np.any(
        lons < -180
    ) or np.any(
        lons > 180
    ):
        raise SeedingError(
            "Particle longitude outside "
            "EPSG:4326 range"
        )

    if np.any(
        lats < -90
    ) or np.any(
        lats > 90
    ):
        raise SeedingError(
            "Particle latitude outside "
            "EPSG:4326 range"
        )

    if not isinstance(
        polygon,
        (Polygon, MultiPolygon),
    ):
        raise SeedingError(
            "Seed geometry must be Polygon "
            "or MultiPolygon"
        )

    for index, (
        lon,
        lat,
    ) in enumerate(
        zip(lons, lats)
    ):

        point = Point(
            float(lon),
            float(lat),
        )

        if not polygon.covers(point):

            raise SeedingError(
                "Particle generated outside "
                "seed geometry: "
                f"index={index}, "
                f"lon={lon}, "
                f"lat={lat}"
            )


def _km_to_degrees(
    km: float,
    latitude: float,
) -> float:
    """
    Approximate kilometers -> latitude degrees.

    Uses approximately:
        111 km = 1 degree

    Args:
        km:
            Distance in kilometers.

        latitude:
            Latitude in degrees.

    Returns:
        Approximate degree distance.
    """

    if km < 0:
        raise ValueError(
            f"km must be >= 0, got {km}"
        )

    if not -90 <= latitude <= 90:
        raise ValueError(
            f"Invalid latitude: {latitude}"
        )

    return km / 111.0

def seed_from_point(
    centroid_lat: float,
    centroid_lon: float,
    radius_km: float,
    seeding_time: datetime,
    config: SeedingConfig,
) -> SeedingResult:
    """
    Seed particles around a point.

    Args:
        centroid_lat:
            Center latitude.

        centroid_lon:
            Center longitude.

        radius_km:
            Radius around center in kilometers.

        seeding_time:
            Simulation seeding time.

        config:
            Seeding configuration.

    Returns:
        SeedingResult
    """
    if not -180 <= centroid_lon <= 180:
        raise ValueError(
            f"Invalid longitude: {centroid_lon}"
        )

    if not -90 <= centroid_lat <= 90:
        raise ValueError(
            f"Invalid latitude: {centroid_lat}"
        )

    if radius_km < 0:
        raise ValueError(
            f"radius_km must be >= 0, got {radius_km}"
        )
    center = Point(
        float(centroid_lon),
        float(centroid_lat),
    )

    buffer_degrees = _km_to_degrees(
        radius_km,
        centroid_lat,
    )

    circle_poly = center.buffer(
        buffer_degrees
    )

    circle_geojson = mapping(
        circle_poly
    )

    return seed_from_polygon(
        circle_geojson,
        seeding_time,
        config,
    )
