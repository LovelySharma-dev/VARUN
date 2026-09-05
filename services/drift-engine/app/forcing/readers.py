"""
Forcing file readers using OpenDrift.

Creates and manages OpenDrift readers for environmental forcing.
"""

import logging
from pathlib import Path
from typing import Optional

from opendrift.readers import reader_netCDF_CF_generic

logger = logging.getLogger(__name__)


def create_forcing_reader(forcing_file: Path):
    """
    Create an OpenDrift reader for a forcing file.

    Args:
        forcing_file: Path to NetCDF forcing file

    Returns:
        OpenDrift reader object

    Raises:
        Exception: If reader creation fails
    """
    if not forcing_file.exists():
        raise FileNotFoundError(f"Forcing file not found: {forcing_file}")

    logger.info(f"Creating OpenDrift reader for {forcing_file.name}")

    try:
        reader = reader_netCDF_CF_generic.Reader(str(forcing_file))
        logger.info(f"Reader created successfully for {forcing_file.name}")
        return reader
    except Exception as e:
        logger.error(f"Failed to create reader for {forcing_file}: {e}")
        raise


def create_combined_readers(
    current_file: Optional[Path] = None,
    wind_file: Optional[Path] = None,
    combined_file: Optional[Path] = None,
) -> list:
    """
    Create multiple readers for forcing files.

    Supports either separate current/wind files or a single combined file.

    Args:
        current_file: Path to current velocity NetCDF
        wind_file: Path to wind velocity NetCDF
        combined_file: Path to combined forcing NetCDF (overrides separate files)

    Returns:
        List of OpenDrift reader objects
    """
    readers = []

    if combined_file is not None:
        logger.info("Using combined forcing file")
        readers.append(create_forcing_reader(combined_file))
    else:
        if current_file is not None:
            logger.info("Creating reader for current file")
            readers.append(create_forcing_reader(current_file))

        if wind_file is not None:
            logger.info("Creating reader for wind file")
            readers.append(create_forcing_reader(wind_file))

    if not readers:
        raise ValueError("No forcing files provided")

    logger.info(f"Created {len(readers)} reader(s)")
    return readers