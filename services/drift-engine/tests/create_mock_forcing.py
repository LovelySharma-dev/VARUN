from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


OUTPUT = Path("data/forcing/mock_combined.nc")


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # Spatial grid
    # ---------------------------------------------------------
    lat = np.linspace(19.0, 19.5, 51)
    lon = np.linspace(72.5, 73.0, 51)

    # ---------------------------------------------------------
    # Time range
    # ---------------------------------------------------------
    time = pd.date_range(
        "2026-09-01T00:00:00",
        "2026-09-03T12:00:00",
        freq="1h",
    )

    shape = (
        len(time),
        len(lat),
        len(lon),
    )

    # ---------------------------------------------------------
    # Mock environmental data
    # ---------------------------------------------------------

    # Ocean current
    current_u = np.full(
        shape,
        0.20,
        dtype=np.float32,
    )

    current_v = np.full(
        shape,
        0.05,
        dtype=np.float32,
    )

    # Wind
    wind_u = np.full(
        shape,
        5.0,
        dtype=np.float32,
    )

    wind_v = np.full(
        shape,
        1.0,
        dtype=np.float32,
    )

    # Significant wave height
    wave_height = np.full(
        shape,
        1.0,
        dtype=np.float32,
    )

    # ---------------------------------------------------------
    # Dataset
    # ---------------------------------------------------------
    ds = xr.Dataset(
        {
            # -------------------------------------------------
            # EXACT OpenDrift variable names
            # -------------------------------------------------

            "x_sea_water_velocity": (
                ("time", "latitude", "longitude"),
                current_u,
                {
                    "standard_name": "eastward_sea_water_velocity",
                    "units": "m s-1",
                    "long_name": "Eastward sea water velocity",
                },
            ),

            "y_sea_water_velocity": (
                ("time", "latitude", "longitude"),
                current_v,
                {
                    "standard_name": "northward_sea_water_velocity",
                    "units": "m s-1",
                    "long_name": "Northward sea water velocity",
                },
            ),

            "x_wind": (
                ("time", "latitude", "longitude"),
                wind_u,
                {
                    "standard_name": "eastward_wind",
                    "units": "m s-1",
                    "long_name": "Eastward wind velocity",
                },
            ),

            "y_wind": (
                ("time", "latitude", "longitude"),
                wind_v,
                {
                    "standard_name": "northward_wind",
                    "units": "m s-1",
                    "long_name": "Northward wind velocity",
                },
            ),

            "sea_surface_wave_significant_height": (
                ("time", "latitude", "longitude"),
                wave_height,
                {
                    "standard_name": "sea_surface_wave_significant_height",
                    "units": "m",
                    "long_name": "Significant wave height",
                },
            ),
        },

        # -----------------------------------------------------
        # Coordinates
        # -----------------------------------------------------
        coords={
            "time": time,

            "latitude": (
                "latitude",
                lat,
                {
                    "standard_name": "latitude",
                    "units": "degrees_north",
                },
            ),

            "longitude": (
                "longitude",
                lon,
                {
                    "standard_name": "longitude",
                    "units": "degrees_east",
                },
            ),
        },

        attrs={
            "title": "VARUN Phase 2 Mock Ocean Forcing",
            "Conventions": "CF-1.8",
        },
    )

    # ---------------------------------------------------------
    # Write NetCDF
    # ---------------------------------------------------------
    ds.to_netcdf(
        OUTPUT,
        engine="scipy",
    )

    print()
    print("=" * 60)
    print("MOCK FORCING CREATED")
    print("=" * 60)
    print(f"File: {OUTPUT.resolve()}")
    print(f"Size: {OUTPUT.stat().st_size / 1024:.2f} KB")
    print()
    print("Variables:")
    for variable in ds.data_vars:
        print(f"  - {variable}")
    print()
    print(f"Time steps : {len(time)}")
    print(f"Latitude   : {lat.min()} → {lat.max()}")
    print(f"Longitude  : {lon.min()} → {lon.max()}")
    print("=" * 60)


if __name__ == "__main__":
    main()