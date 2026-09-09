"""
Domain-specific exceptions for VARUN Phase 2.

All Phase 2 operations should raise these exceptions (not generic ones)
for proper error handling and API responses.
"""

from typing import Any, Optional


class Phase2Error(Exception):
    """Base exception for all Phase 2 errors."""

    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN_ERROR",
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert to API-friendly dict."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class ForcingError(Phase2Error):
    """Base exception for forcing-related errors."""

    pass


class ForcingValidationError(ForcingError):
    """Forcing validation failed."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message, code="FORCING_VALIDATION_FAILED", details=details
        )


class ForcingCoverageError(ForcingError):
    """Forcing does not cover required simulation period."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message, code="FORCING_OUT_OF_RANGE", details=details
        )


class ForcingReadError(ForcingError):
    """Failed to read forcing file."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message, code="FORCING_READ_ERROR", details=details
        )


class InvalidSpillGeometryError(Phase2Error):
    """Spill polygon geometry is invalid."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message, code="INVALID_SPILL_GEOMETRY", details=details
        )


class SeedingError(Phase2Error):
    """Particle seeding failed."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message, code="SEEDING_ERROR", details=details
        )


class SimulationConfigurationError(Phase2Error):
    """Simulation configuration is invalid."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message, code="INVALID_CONFIGURATION", details=details
        )


class SimulationExecutionError(Phase2Error):
    """Simulation execution failed."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message, code="SIMULATION_FAILED", details=details
        )


class ArtifactGenerationError(Phase2Error):
    """Failed to generate output artifacts."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message, code="ARTIFACT_GENERATION_FAILED", details=details
        )


class TimeNormalizationError(Phase2Error):
    """Failed to normalize time."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message, code="TIME_NORMALIZATION_ERROR", details=details
        )