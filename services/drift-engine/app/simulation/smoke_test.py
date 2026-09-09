"""
VARUN Phase 2 — OpenDrift Smoke Test

This test verifies:

1. OpenDrift is installed correctly
2. OpenOil can be imported
3. OpenOil can be instantiated
4. Environmental fallback forcing works
5. Oil particles can be seeded
6. A basic simulation can run
7. Trajectory data is available
8. NetCDF output can be generated
"""

import logging
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np


logger = logging.getLogger(__name__)


def test_opendrift_smoke() -> bool:
    """Test basic OpenDrift/OpenOil functionality."""

    print("\n" + "=" * 60)
    print("VARUN Phase 2 OpenDrift Smoke Test")
    print("=" * 60)

    try:
        from opendrift.models.openoil import OpenOil

        print("✓ OpenDrift import successful")

    except ImportError as e:
        print(f"✗ Failed to import OpenDrift: {e}")
        return False

    try:
        o = OpenOil(loglevel=logging.WARNING)

        print("✓ OpenOil model instantiated")

    except Exception as e:
        print(f"✗ Failed to create OpenOil: {e}")
        return False

    try:
        # Ocean current - X direction
        o.set_config(
            "environment:fallback:x_sea_water_velocity",
            0.1,
        )

        # Ocean current - Y direction
        o.set_config(
            "environment:fallback:y_sea_water_velocity",
            0.0,
        )

        # Wind - X direction
        o.set_config(
            "environment:fallback:x_wind",
            5.0,
        )

        # Wind - Y direction
        o.set_config(
            "environment:fallback:y_wind",
            0.0,
        )

        # Assume no land for this simple test
        o.set_config(
            "environment:fallback:land_binary_mask",
            0,
        )

        print("✓ Constant environmental forcing configured")

    except Exception as e:
        print(f"✗ Failed to configure environmental forcing: {e}")
        return False

    try:
        lons = np.array([5.0, 5.1])
        lats = np.array([60.0, 60.1])

        start_time = datetime(
            2020,
            1,
            1,
            12,
            0,
            0,
        )

        o.seed_elements(
            lon=lons,
            lat=lats,
            time=start_time,
        )

        print(f"✓ Particles seeded: {len(lats)} particles")

    except Exception as e:
        print(f"✗ Failed to seed particles: {e}")
        return False

    try:
        o.run(
        duration=timedelta(hours=1),
        time_step=timedelta(minutes=30),
    )

        print("✓ Simulation ran successfully")

    except Exception as e:
        print(f"✗ Simulation failed: {e}")
        return False

    try:
        result = o.result

        if result is None:
            print("✗ OpenDrift returned no result dataset")
            return False

        if "lon" not in result:
            print("✗ Longitude data missing from result")
            return False

        if "lat" not in result:
            print("✗ Latitude data missing from result")
            return False

        if "time" not in result.coords:
            print("✗ Time coordinate missing from result")
            return False

        lon_data = result["lon"]
        lat_data = result["lat"]
        time_data = result["time"]

        print("✓ Trajectory result available")

        print(f"  - Longitude shape: {lon_data.shape}")
        print(f"  - Latitude shape: {lat_data.shape}")
        print(f"  - Time shape: {time_data.shape}")

        print(
            f"  - Lon range: "
            f"[{float(lon_data.min()):.3f}, "
            f"{float(lon_data.max()):.3f}]"
        )

        print(
            f"  - Lat range: "
            f"[{float(lat_data.min()):.3f}, "
            f"{float(lat_data.max()):.3f}]"
        )

    except Exception as e:
        print(f"✗ Failed to extract trajectory: {e}")
        return False

    try:
        with tempfile.TemporaryDirectory() as tmpdir:

            outfile = Path(tmpdir) / "test_output.nc"

            result = o.result

            if result is None:
                print("✗ No simulation result available")
                return False

            ds = result.copy()

            # Fix invalid attrs
            for key, value in list(ds.attrs.items()):
                if isinstance(value, type):
                    ds.attrs[key] = str(value)

            for var in ds.variables:
                for key, value in list(ds[var].attrs.items()):
                    if isinstance(value, type):
                        ds[var].attrs[key] = str(value)

            ds.to_netcdf(str(outfile))

            if not outfile.exists():
                print("✗ NetCDF file not created")
                return False

            size_mb = outfile.stat().st_size / (1024 * 1024)

            print(f"✓ NetCDF output created ({size_mb:.2f} MB)")

    except Exception as e:
        print(f"✗ NetCDF writing failed: {e}")
        return False

    print("\n" + "=" * 60)
    print("✓ ALL OPENDRIFT SMOKE TESTS PASSED!")
    print("=" * 60 + "\n")

    return True


if __name__ == "__main__":
    success = test_opendrift_smoke()

    sys.exit(0 if success else 1)