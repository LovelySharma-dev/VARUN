"""
Forcing file audit and validation.

Validates individual forcing files by their role:
- Current-only files must contain eastward + northward currents.
- Wind-only files must contain eastward + northward 10m winds.
- A combined file may contain either/both forcing types.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import xarray as xr

from app.exceptions import ForcingReadError
from app.forcing.models import (
    ForcingAuditResult,
    SpatialBounds,
    TemporalBounds,
    VariableInfo,
)
from app.utils import normalize_simulation_time

logger = logging.getLogger(__name__)

# Variable 
CURRENT_U_NAMES = {
    "uo",
    "eastward_sea_water_velocity",
    "current_u",
    "u_current",
}

CURRENT_V_NAMES = {
    "vo",
    "northward_sea_water_velocity",
    "current_v",
    "v_current",
}

WIND_U_NAMES = {
    "u10",
    "10u",
    "eastward_wind",
    "eastward_wind_at_10m",
}

WIND_V_NAMES = {
    "v10",
    "10v",
    "northward_wind",
    "northward_wind_at_10m",
}


LAT_NAMES = ["latitude", "lat", "y"]
LON_NAMES = ["longitude", "lon", "x"]

TIME_NAMES = {
    "time",
    "valid_time",
}


# Public API
def audit_forcing_file(
    file_path: Path,
    required_type: Optional[str] = None,
) -> ForcingAuditResult:
    """
    Audit one forcing NetCDF file.

    Args:
        file_path:
            Path to NetCDF file.

        required_type:
            Optional role of this forcing file:
                "current"
                "wind"
                None

            If None, the file is accepted if it contains at least one
            complete forcing pair.

    Returns:
        ForcingAuditResult
    """

    file_path = Path(file_path)

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


    if not file_path.exists():
        result.errors.append(f"File does not exist: {file_path}")
        return result

    if not file_path.is_file():
        result.errors.append(f"Not a file: {file_path}")
        return result

    result.file_size_mb = file_path.stat().st_size / (1024 * 1024)

    try:
        ds = xr.open_dataset(file_path)
    except Exception as exc:
        result.errors.append(f"Cannot open as NetCDF: {exc}")
        return result

    result.is_valid_netcdf = True

    try:
        lat_name = _find_coordinate(ds, LAT_NAMES)
        lon_name = _find_coordinate(ds, LON_NAMES)
        time_name = _find_coordinate(ds, TIME_NAMES)

        has_lat = lat_name is not None
        has_lon = lon_name is not None
        has_time = time_name is not None

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

        if has_lat and has_lon:
            lat_data = np.asarray(ds[lat_name].values)
            lon_data = np.asarray(ds[lon_name].values)

            lat_min = float(np.nanmin(lat_data))
            lat_max = float(np.nanmax(lat_data))
            lon_min = float(np.nanmin(lon_data))
            lon_max = float(np.nanmax(lon_data))

            result.spatial_bounds = SpatialBounds(
                lat_min=lat_min,
                lat_max=lat_max,
                lon_min=lon_min,
                lon_max=lon_max,
            )

            if lat_data.ndim == 1 and not _is_monotonic(lat_data):
                result.warnings.append("Latitude is not monotonic")

            if lon_data.ndim == 1 and not _is_monotonic(lon_data):
                result.warnings.append("Longitude is not monotonic")

        if has_time:
            time_data = np.asarray(ds[time_name].values)

            if len(time_data) == 0:
                result.errors.append("Time coordinate is empty")

            elif len(time_data) == 1:
                result.errors.append(
                    "Less than 2 time steps in forcing"
                )

                try:
                    t = normalize_simulation_time(
                        time_data[0],
                        "time",
                    )

                    result.temporal_bounds = TemporalBounds(
                        time_start=t,
                        time_end=t,
                    )
                except Exception as exc:
                    result.errors.append(
                        f"Cannot parse time coordinate: {exc}"
                    )

            else:
                try:
                    time_start = normalize_simulation_time(
                        time_data[0],
                        "time_start",
                    )

                    time_end = normalize_simulation_time(
                        time_data[-1],
                        "time_end",
                    )

                    result.temporal_bounds = TemporalBounds(
                        time_start=time_start,
                        time_end=time_end,
                    )

                    if not _is_time_monotonic(time_data):
                        result.errors.append(
                            "Time is not monotonic"
                        )

                except Exception as exc:
                    result.errors.append(
                        f"Cannot parse time coordinate: {exc}"
                    )

        current_u = _find_variable(
            ds,
            CURRENT_U_NAMES,
        )

        current_v = _find_variable(
            ds,
            CURRENT_V_NAMES,
        )

        wind_u = _find_variable(
            ds,
            WIND_U_NAMES,
        )

        wind_v = _find_variable(
            ds,
            WIND_V_NAMES,
        )

        if current_u:
            result.current_variables_found.append(current_u)

        if current_v:
            result.current_variables_found.append(current_v)

        if wind_u:
            result.wind_variables_found.append(wind_u)

        if wind_v:
            result.wind_variables_found.append(wind_v)

        if required_type == "current":

            if not current_u:
                result.errors.append(
                    "No eastward current velocity found"
                )

            if not current_v:
                result.errors.append(
                    "No northward current velocity found"
                )

            if not wind_u:
                result.warnings.append(
                    "No eastward wind found (current-only file)"
                )

            if not wind_v:
                result.warnings.append(
                    "No northward wind found (current-only file)"
                )

        elif required_type == "wind":

            if not wind_u:
                result.errors.append(
                    "No eastward 10m wind found"
                )

            if not wind_v:
                result.errors.append(
                    "No northward 10m wind found"
                )

            if not current_u:
                result.warnings.append(
                    "No eastward current velocity found (wind-only file)"
                )

            if not current_v:
                result.warnings.append(
                    "No northward current velocity found (wind-only file)"
                )

        else:
            has_current_pair = bool(current_u and current_v)
            has_wind_pair = bool(wind_u and wind_v)

            if not has_current_pair and not has_wind_pair:
                result.errors.append(
                    "No complete current or wind forcing pair found"
                )

        var_mapping = {}

        if current_u:
            var_mapping[current_u] = "current_u"

        if current_v:
            var_mapping[current_v] = "current_v"

        if wind_u:
            var_mapping[wind_u] = "wind_u"

        if wind_v:
            var_mapping[wind_v] = "wind_v"

        for var_name, standard_name in var_mapping.items():

            if var_name not in ds.data_vars:
                continue

            var = ds[var_name]

            units = var.attrs.get(
                "units",
                "unknown",
            )

            if units not in {"m/s", "m s-1", "m s**-1"}:
                result.warnings.append(
                    f"{var_name} has units '{units}' "
                    f"(expected m/s or m s-1)"
                )

            data = np.asarray(var.values)

            if data.size == 0:
                result.errors.append(
                    f"{var_name} contains no data"
                )
                continue

            if np.issubdtype(data.dtype, np.floating):
                missing_count = np.isnan(data).sum()
            else:
                missing_count = 0

            missing_fraction = (
                float(missing_count) / float(data.size)
            )

            result.variables[var_name] = VariableInfo(
                name=var_name,
                standard_name=standard_name,
                units=units,
                shape=tuple(data.shape),
                missing_fraction=missing_fraction,
            )

            if missing_fraction > 0.5:
                result.errors.append(
                    f"{var_name} is "
                    f"{missing_fraction * 100:.1f}% missing"
                )

        result.passed = (
            result.is_valid_netcdf
            and len(result.errors) == 0
        )

    except Exception as exc:
        result.errors.append(
            f"Unexpected forcing audit error: {exc}"
        )

    finally:
        ds.close()

    return result


def _find_coordinate(
    ds: xr.Dataset,
    names: list[str],
) -> Optional[str]:

    for name in names:

        if name in ds.coords:
            return name

        if name in ds.data_vars:
            return name

    return None


def _find_variable(
    ds: xr.Dataset,
    names: set[str],
) -> Optional[str]:

    for name in names:

        if name in ds.data_vars:
            return name

    return None


def _is_monotonic(
    arr: np.ndarray,
) -> bool:

    arr = np.asarray(arr)

    if len(arr) < 2:
        return True

    diffs = np.diff(arr)

    return bool(
        np.all(diffs > 0)
        or np.all(diffs < 0)
    )


def _is_time_monotonic(
    time_data: np.ndarray,
) -> bool:

    if len(time_data) < 2:
        return True

    try:

        times = np.asarray(time_data)

        if np.issubdtype(
            times.dtype,
            np.datetime64,
        ):
            return bool(
                np.all(
                    np.diff(times)
                    > np.timedelta64(0, "ns")
                )
            )

        normalized = [
            normalize_simulation_time(
                t,
                "time",
            )
            for t in times
        ]

        return all(
            normalized[i]
            < normalized[i + 1]
            for i in range(len(normalized) - 1)
        )

    except Exception as exc:

        logger.warning(
            "Unable to determine time monotonicity: %s",
            exc,
        )

        return False


def cli_main():

    import sys
    import click

    @click.command()
    @click.argument(
        "file_path",
        type=click.Path(exists=True),
    )
    @click.option(
        "--type",
        "required_type",
        type=click.Choice(
            ["current", "wind"],
        ),
        default=None,
    )
    def audit(
        file_path: str,
        required_type: Optional[str],
    ):
        """Audit a forcing NetCDF file."""

        path = Path(file_path)

        result = audit_forcing_file(
            path,
            required_type=required_type,
        )

        print(result.summary())

        sys.exit(
            0 if result.passed else 1
        )

    audit()