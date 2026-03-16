"""GarmentSpec protocol and BodiceGarmentSpec implementation.

Defines the garment-agnostic interface that the self-correction engine
uses to operate on any garment type.  BodiceGarmentSpec wraps existing
bodice logic (ParsonsSloperGenerator, bodice stress formulas, bodice
correction logic) without modifying any frozen files.
"""

from __future__ import annotations

import dataclasses
from typing import Protocol, runtime_checkable

from agentic_pattern_engine.models import (
    BodiceSloper,
    CorrectionStrategy,
    CorrectionType,
    DartGeometry,
    FitIssue,
    FitIssueType,
    MeasurementProfile,
    PatternPiece,
    Point2D,
)


# ---------------------------------------------------------------------------
# GarmentSpec protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class GarmentSpec(Protocol):
    """Garment-agnostic interface for the self-correction engine."""

    @property
    def garment_type(self) -> str:
        """Return garment identifier, e.g. 'bodice', 'skirt'."""
        ...

    @property
    def measurement_fields(self) -> list[str]:
        """Required measurement field names for this garment type."""
        ...

    @property
    def fit_regions(self) -> list[str]:
        """Supported fit region names for stress analysis."""
        ...

    @property
    def tension_thresholds(self) -> dict[str, float]:
        """Per-region tension thresholds in Pascals."""
        ...

    def validate_profile(
        self, profile: MeasurementProfile,
    ) -> list[str]:
        """Validate that the profile has all required fields in range."""
        ...

    def generate_initial_pieces(
        self, profile: MeasurementProfile,
    ) -> list[PatternPiece]:
        """Generate initial pattern pieces from measurements."""
        ...

    def compute_stress(
        self,
        pieces: list[PatternPiece],
        profile: MeasurementProfile,
    ) -> dict[str, float]:
        """Compute per-region stress given pieces and profile."""
        ...

    def plan_corrections(
        self,
        fit_issues: list[FitIssue],
        pieces: list[PatternPiece],
        profile: MeasurementProfile,
        dampening_factor: float,
    ) -> list[CorrectionStrategy]:
        """Plan corrections for detected fit issues."""
        ...

    def apply_corrections(
        self,
        pieces: list[PatternPiece],
        corrections: list[CorrectionStrategy],
    ) -> list[PatternPiece]:
        """Apply corrections and return updated pattern pieces."""
        ...

    def validate_geometry(
        self, pieces: list[PatternPiece],
    ) -> list[str]:
        """Validate resulting geometry. Return errors if invalid."""
        ...


# ---------------------------------------------------------------------------
# BodiceGarmentSpec — wraps existing bodice logic
# ---------------------------------------------------------------------------

class BodiceGarmentSpec:
    """GarmentSpec implementation for bodice slopers.

    Delegates to ParsonsSloperGenerator and existing bodice stress /
    correction logic.  Does NOT modify any frozen files.
    """

    def __init__(self) -> None:
        from agentic_pattern_engine.geometry_corrector import (
            DartEaseGeometryCorrector,
        )
        from agentic_pattern_engine.simulation_engine import (
            MassSpringSimulationEngine,
        )
        from agentic_pattern_engine.sloper_generator import (
            ParsonsSloperGenerator,
        )

        self._generator = ParsonsSloperGenerator()
        self._sim_engine = MassSpringSimulationEngine()
        self._corrector = DartEaseGeometryCorrector()
        self._last_sloper: BodiceSloper | None = None

    # -- properties --------------------------------------------------------

    @property
    def garment_type(self) -> str:
        return "bodice"

    @property
    def measurement_fields(self) -> list[str]:
        return [
            "chest", "waist", "hip",
            "shoulder_width", "torso_length",
        ]

    @property
    def fit_regions(self) -> list[str]:
        return [
            "bust", "waist", "shoulder", "armhole",
            "side_seam", "center_front", "center_back",
        ]

    @property
    def tension_thresholds(self) -> dict[str, float]:
        return {
            "bust": 60.0,
            "waist": 50.0,
            "shoulder": 80.0,
            "armhole": 70.0,
            "side_seam": 55.0,
            "center_front": 50.0,
            "center_back": 50.0,
        }

    # -- protocol methods --------------------------------------------------

    def validate_profile(
        self, profile: MeasurementProfile,
    ) -> list[str]:
        return profile.validate()

    def generate_initial_pieces(
        self, profile: MeasurementProfile,
    ) -> list[PatternPiece]:
        sloper = self._generator.generate(profile)
        self._last_sloper = sloper
        return [sloper.front_bodice, sloper.back_bodice]

    def compute_stress(
        self,
        pieces: list[PatternPiece],
        profile: MeasurementProfile,
    ) -> dict[str, float]:
        sloper = self._reconstruct_sloper(pieces, profile)
        return self._sim_engine._compute_regional_stresses(
            sloper, profile,
        )

    def plan_corrections(
        self,
        fit_issues: list[FitIssue],
        pieces: list[PatternPiece],
        profile: MeasurementProfile,
        dampening_factor: float,
    ) -> list[CorrectionStrategy]:
        sloper = self._reconstruct_sloper(pieces, profile)
        return self._corrector.plan_corrections(
            fit_issues, sloper, profile, dampening_factor,
        )

    def apply_corrections(
        self,
        pieces: list[PatternPiece],
        corrections: list[CorrectionStrategy],
    ) -> list[PatternPiece]:
        if self._last_sloper is None:
            raise RuntimeError(
                "No sloper available; call generate_initial_pieces first"
            )
        sloper = self._reconstruct_sloper(
            pieces, self._last_sloper.profile,
        )
        updated = self._corrector.apply_to_sloper(sloper, corrections)
        self._last_sloper = updated
        return [updated.front_bodice, updated.back_bodice]

    def validate_geometry(
        self, pieces: list[PatternPiece],
    ) -> list[str]:
        errors: list[str] = []
        for piece in pieces:
            label = piece.label
            if (
                len(piece.outline) < 2
                or piece.outline[0] != piece.outline[-1]
            ):
                errors.append(f"{label}: outline is not closed")
            if len(piece.darts) < 1:
                errors.append(
                    f"{label}: must have at least one dart"
                )
            if piece.seam_allowance <= 0:
                errors.append(
                    f"{label}: seam_allowance must be > 0"
                )
            gl = piece.grain_line
            if gl.start == gl.end:
                errors.append(
                    f"{label}: grain_line is degenerate (zero length)"
                )
            if len(piece.notch_marks) < 1:
                errors.append(
                    f"{label}: must have at least one notch mark"
                )
        return errors

    # -- internal helpers --------------------------------------------------

    def _reconstruct_sloper(
        self,
        pieces: list[PatternPiece],
        profile: MeasurementProfile,
    ) -> BodiceSloper:
        """Rebuild a BodiceSloper from pattern pieces.

        Uses the cached sloper for ease / metadata values, replacing
        only the front and back pieces with the current versions.
        """
        if self._last_sloper is not None:
            return dataclasses.replace(
                self._last_sloper,
                front_bodice=pieces[0],
                back_bodice=pieces[1],
            )
        # Fallback: generate fresh sloper and swap pieces
        sloper = self._generator.generate(profile)
        self._last_sloper = sloper
        return dataclasses.replace(
            sloper,
            front_bodice=pieces[0],
            back_bodice=pieces[1],
        )
