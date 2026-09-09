"""
Forcing file audit and validation.

Comprehensive validation of NetCDF forcing files.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import xarray as xr
from app.exceptions import ForcingReadError, ForcingValidationError
from app.forcing.models import (
    ForcingAuditResult,
    SpatialBounds,
    TemporalBounds,
    VariableInfo,
)
from app.utils import normalize_simulation_time

logger = logging.getLogger(__name__)

# Variable name aliases
CURRENT_U_NAMES = [
    "eastward_sea_water_velocity",
    "u",
    "uo",
    "water_u",
]
CURRENT_V_NAMES = [
    "northward_sea_water_velocity",
    "v",
    "vo",
    "water_v",
]
WIND_U_NAMES = [
    "eastward_wind",
    "u10",
    "wind_u",
    "10u",
]
WIND_V_NAMES = [
    "northward_wind",
    "v10",
    "wind_v",
    "10v",
]

# Latitude/longitude aliases
LAT_NAMES = ["latitude", "lat", "y"]
LON_NAMES = ["longitude", "lon", "x"]
TIME_NAMES = ["time", "time_counter"]


def audit_forcing_file(file_path: Path) -> ForcingAuditResult:
    """
    Audit a forcing NetCDF file.

    Args:
        file_path: Path to NetCDF file

    Returns:
        ForcingAuditResult with detailed validation info

    Raises:
        ForcingReadError: If file cannot be read
    """
    result = ForcingAuditResult(
        file_path=file_path,
        passed=False,
        errors=[],
        warnings=[],
        variables={},
        coordinates={},
        file_size_mb=0,
        is_valid_netcdf=False,
    )

    # Check file exists and is readable
    if not file_path.exists():
        result.errors.append(f"File does not exist: {file_path}")
        return result

    if not file_path.is_file():
        result.errors.append(f"Not a file: {file_path}")
        return result

    # Check file size
    result.file_size_mb = file_path.stat().st_size / (1024 * 1024)

    # Try to open as NetCDF
    try:
        ds = xr.open_dataset(file_path)
    except Exception as e:
        result.errors.append(f"Cannot open as NetCDF: {e}")
        return result

    result.is_valid_netcdf = True

    try:
        # Check coordinates
        has_lat = _find_coordinate(ds, LAT_NAMES) is not None
        has_lon = _find_coordinate(ds, LON_NAMES) is not None
        has_time = _find_coordinate(ds, TIME_NAMES) is not None

        result.coordinates = {
            "latitude": has_lat,
            "longitude": has_lon,
            "time": has_time,
        }

        if not has_lat:
            result.errors.append("No latitude coordinate found")
        if not has_lon:
            result.errors.append("No longitude coordinate found")
        if not has_time:
            result.errors.append("No time coordinate found")

        # Get spatial bounds
        if has_lat and has_lon:
            lat_name = _find_coordinate(ds, LAT_NAMES)
            lon_name = _find_coordinate(ds, LON_NAMES)

            lat_data = ds[lat_name].values
            lon_data = ds[lon_name].values

            # Handle multi-dimensional coordinates
            if lat_data.ndim > 1:
                lat_min, lat_max = np.nanmin(lat_data), np.nanmax(lat_data)
            else:
                lat_min, lat_max = np.min(lat_data), np.max(lat_data)

            if lon_data.ndim > 1:
                lon_min, lon_max = np.nanmin(lon_data), np.nanmax(lon_data)
            else:
                lon_min, lon_max = np.min(lon_data), np.max(lon_data)

            result.spatial_bounds = SpatialBounds(
                lat_min=float(lat_min),
                lat_max=float(lat_max),
                lon_min=float(lon_min),
                lon_max=float(lon_max),
            )

            # Check if coordinates are monotonic
            if lat_data.ndim == 1:
                if not _is_monotonic(lat_data):
                    result.warnings.append("Latitude is not monotonic")
            if lon_data.ndim == 1:
                if not _is_monotonic(lon_data):
                    result.warnings.append("Longitude is not monotonic")

        # Get temporal bounds
        if has_time:
            time_name = _find_coordinate(ds, TIME_NAMES)
            time_data = ds[time_name].values

            if len(time_data) < 2:
                result.errors.append("Less than 2 time steps in forcing")
            else:
                try:
                    time_start = normalize_simulation_time(
                        time_data[0], "time_start"
                    )
                    time_end = normalize_simulation_time(
                        time_data[-1], "time_end"
                    )

                    result.temporal_bounds = TemporalBounds(
                        time_start=time_start,
                        time_end=time_end,
                    )

                    # Check if time is monotonic
                    if not _is_time_monotonic(time_data):
                        result.errors.append("Time is not monotonic")

                except Exception as e:
                    result.errors.append(f"Cannot parse time coordinate: {e}")

        # Check for required variables
        current_u = _find_variable(ds, CURRENT_U_NAMES)
        current_v = _find_variable(ds, CURRENT_V_NAMES)
        wind_u = _find_variable(ds, WIND_U_NAMES)
        wind_v = _find_variable(ds, WIND_V_NAMES)

        if current_u:
            result.current_variables_found.append(current_u)
        else:
            result.warnings.append("No eastward current velocity found")

        if current_v:
            result.current_variables_found.append(current_v)
        else:
            result.warnings.append("No northward current velocity found")

        if wind_u:
            result.wind_variables_found.append(wind_u)
        else:
            result.warnings.append("No eastward wind found")

        if wind_v:
            result.wind_variables_found.append(wind_v)
        else:
            result.warnings.append("No northward wind found")

        # Map variables
        var_mapping = {}
        if current_u:
            var_mapping[current_u] = "current_u"
        if current_v:
            var_mapping[current_v] = "current_v"
        if wind_u:
            var_mapping[wind_u] = "wind_u"
        if wind_v:
            var_mapping[wind_v] = "wind_v"

        # Audit each variable
        for var_name in var_mapping.keys():
            if var_name in ds.data_vars:
                var = ds[var_name]
                units = var.attrs.get("units", "unknown")

                # Validate units
                if units not in ["m/s", "m s-1"]:
                    result.warnings.append(
                        f"{var_name} has units '{units}' (expected m/s or m s-1)"
                    )

                # Calculate missing fraction
                data = var.values
                if data.dtype == "float":
                    missing_count = np.isnan(data).sum()
                else:
                    missing_count = 0

                missing_fraction = float(missing_count) / data.size

                result.variables[var_name] = VariableInfo(
                    name=var_name,
                    standard_name=var_mapping.get(var_name),
                    units=units,
                    shape=tuple(data.shape),
                    missing_fraction=missing_fraction,
                )

                if missing_fraction > 0.5:
                    result.errors.append(
                        f"{var_name} is {missing_fraction*100:.1f}% missing"
                    )

        # Final decision
        result.passed = (
            len(result.errors) == 0
            and result.is_valid_netcdf
            and len(result.current_variables_found) >= 2
            and len(result.wind_variables_found) >= 2
        )

    finally:
        ds.close()

    return result


def _find_coordinate(ds: xr.Dataset, names: list[str]) -> Optional[str]:
    """Find coordinate by list of possible names."""
    for name in names:
        if name in ds.coords:
            return name
        if name in ds.data_vars:
            return name
    return None


def _find_variable(ds: xr.Dataset, names: list[str]) -> Optional[str]:
    """Find variable by list of possible names."""
    for name in names:
        if name in ds.data_vars:
            return name
    return None


def _is_monotonic(arr: np.ndarray) -> bool:
    """Check if array is monotonic."""
    if len(arr) < 2:
        return True
    diffs = np.diff(arr)
    return np.all(diffs > 0) or np.all(diffs < 0)


def _is_time_monotonic(time_data: np.ndarray) -> bool:
    """Check if time coordinate is monotonic."""
    if len(time_data) < 2:
        return True

    try:
        times = np.array(
            [normalize_simulation_time(t, "time") for t in time_data]
        )
        diffs = np.diff(times)
        return np.all(diffs > np.timedelta64(0))
    except Exception:
        return False


def cli_main():
    """CLI entry point for forcing audit."""
    import sys

    import click

    @click.command()
    @click.argument("file_path", type=click.Path(exists=True))
    def audit(file_path: str):
        """Audit a forcing NetCDF file."""
        path = Path(file_path)
        result = audit_forcing_file(path)
        print(result.summary())
        sys.exit(0 if result.passed else 1)

    audit()