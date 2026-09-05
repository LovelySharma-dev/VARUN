"""Create synthetic demo forcing data for testing."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)


def create_demo_forcing(output_path: Path, duration_hours: 72):
    """
    Create a synthetic CF-compliant forcing file.

    Args:
        output_path: Where to save the NetCDF file
        duration_hours: Duration of forcing (hours)
    """
    print(f"Creating synthetic forcing file: {output_path}")

    # Domain (around India coast)
    lat = np.linspace(18.0, 20.0, 21)  # 21 points
    lon = np.linspace(71.0, 74.0, 31)  # 31 points

    # Time (hourly for duration)
    start_time = datetime(2026, 9, 1, 0, 0, 0)
    times = [start_time + timedelta(hours=i) for i in range(duration_hours + 1)]

    # Create synthetic data
    n_times = len(times)
    n_lat = len(lat)
    n_lon = len(lon)

    # Synthetic currents (rotating field)
    print(f"  Grid: {n_lat}×{n_lon} over {n_times} time steps")

    # Initialize arrays
    u_current = np.zeros((n_times, n_lat, n_lon))
    v_current = np.zeros((n_times, n_lat, n_lon))
    u_wind = np.zeros((n_times, n_lat, n_lon))
    v_wind = np.zeros((n_times, n_lat, n_lon))

    # Fill with synthetic but realistic data
    for t in range(n_times):
        phase = 2 * np.pi * t / n_times

        # Currents - weak rotating field
        for i in range(n_lat):
            for j in range(n_lon):
                angle = np.arctan2(lat[i] - 19.0, lon[j] - 72.5)
                speed = 0.2  # m/s average

                u_current[t, i, j] = speed * np.cos(angle + phase)
                v_current[t, i, j] = speed * np.sin(angle + phase)

                # Wind - stronger and more variable
                wind_speed = 5.0 + 2.0 * np.sin(angle + phase)  # m/s

                u_wind[t, i, j] = wind_speed * np.cos(angle + phase * 2)
                v_wind[t, i, j] = wind_speed * np.sin(angle + phase * 2)

    # Create xarray Dataset
    ds = xr.Dataset(
        {
            "eastward_sea_water_velocity": (["time", "latitude", "longitude"], u_current),
            "northward_sea_water_velocity": (["time", "latitude", "longitude"], v_current),
            "eastward_wind": (["time", "latitude", "longitude"], u_wind),
            "northward_wind": (["time", "latitude", "longitude"], v_wind),
        },
        coords={
            "time": times,
            "latitude": lat,
            "longitude": lon,
        },
    )

    # Add attributes
    ds["eastward_sea_water_velocity"].attrs = {
        "long_name": "Eastward Sea Water Velocity",
        "units": "m/s",
        "standard_name": "eastward_sea_water_velocity",
    }
    ds["northward_sea_water_velocity"].attrs = {
        "long_name": "Northward Sea Water Velocity",
        "units": "m/s",
        "standard_name": "northward_sea_water_velocity",
    }
    ds["eastward_wind"].attrs = {
        "long_name": "Eastward Wind",
        "units": "m/s",
        "standard_name": "eastward_wind",
    }
    ds["northward_wind"].attrs = {
        "long_name": "Northward Wind",
        "units": "m/s",
        "standard_name": "northward_wind",
    }

    ds.attrs = {
        "Conventions": "CF-1.8",
        "title": "Synthetic demo forcing for VARUN Phase 2",
        "source": "Synthetic for testing - NOT REAL DATA",
        "history": f"Created {datetime.now().isoformat()}",
    }

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(output_path)

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"  ✓ Forcing file created ({file_size_mb:.2f} MB)")
    print(f"  Domain: lat [{lat.min():.1f}, {lat.max():.1f}] lon [{lon.min():.1f}, {lon.max():.1f}]")
    print(f"  Time: {times[0].isoformat()} to {times[-1].isoformat()}")


if __name__ == "__main__":
    from pathlib import Path

    project_root = Path(__file__).parent.parent
    output_file = project_root / "data" / "forcing" / "demo_forcing.nc"

    create_demo_forcing(output_file, duration_hours=72)
    print(f"\n✓ Demo forcing created successfully\n")