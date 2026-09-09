"""
VARUN Phase 2 — Oil Spill Drift Simulation Engine

A production-ready offshore oil drift simulation system using OpenDrift.
"""

__version__ = "0.2.0"
__author__ = "VARUN Engineering"

# Configure logging at package level
import logging

logging.getLogger("opendrift").setLevel(logging.INFO)
logging.getLogger("opendrift.models.basebulk").setLevel(logging.WARNING)