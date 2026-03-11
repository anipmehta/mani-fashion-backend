"""Sloper Generator — Parsons-method bodice drafting in pure Python.

Implements the SloperGenerator protocol using simplified Parsons-method
drafting formulas. No external PyGarment dependency required.
"""

from __future__ import annotations

import dataclasses
import math
import uuid
from datetime import datetime, timezone

from agentic_pattern_engine.models import (
    BodiceSloper,
    CorrectionStrategy,
    CorrectionType,
    DartGeometry,
    Line2D,
    MeasurementProfile,
    PatternPiece,
    Point2D,
)

# Default ease values (cm)
DEFAULT_BUST_EASE = 5.0
DEFAULT_WAIST_EASE = 3.0
DEFAULT_SEAM_ALLOWANCE = 1.5  # cm


class ParsonsSloperGenerator:
    """Generate bodice slopers using simplified Parsons-method drafting."""

    def generate(self, profile: MeasurementProfile) -> BodiceSloper:
        """Generate an initial bodice sloper from a MeasurementProfile.

        Raises ``ValueError`` if the profile fails validation.
        """
        errors = profile.validate()
        if errors:
            raise ValueError(f"Invalid MeasurementProfile: {'; '.join(errors)}")

        bust_ease = DEFAULT_BUST_EASE
        waist_ease = DEFAULT_WAIST_EASE

        front = self._draft_front(profile, bust_ease, waist_ease)
        back = self._draft_back(profile, bust_ease, waist_ease)

        return BodiceSloper(
            sloper_id=str(uuid.uuid4()),
            profile=profile,
            front_bodice=front,
            back_bodice=back,
            bust_ease=bust_ease,
            waist_ease=waist_ease,
            metadata={
                "engine_version": "0.1.0",
                "method": "parsons",
            },
        )


    # ------------------------------------------------------------------
    # Front bodice drafting (simplified Parsons)
    # ------------------------------------------------------------------

    @staticmethod
    def _draft_front(
        profile: MeasurementProfile,
        bust_ease: float,
        waist_ease: float,
    ) -> PatternPiece:
        chest = profile.chest
        waist = profile.waist
        shoulder_width = profile.shoulder_width
        torso_length = profile.torso_length

        width = chest / 4.0 + bust_ease / 2.0
        length = torso_length

        # Shoulder slope: drops ~3 cm over half-shoulder width
        shoulder_half = shoulder_width / 2.0
        shoulder_drop = 3.0

        # Key construction points (origin at top-left = center front neckline)
        p_top_left = Point2D(0.0, 0.0)
        p_shoulder = Point2D(shoulder_half, -shoulder_drop)
        p_armhole_top = Point2D(width, -shoulder_drop - 2.0)
        p_armhole_mid = Point2D(width, -(length * 0.4))
        p_side_bottom = Point2D(width, -length)
        p_bottom_right = Point2D(width, -length)
        p_bottom_left = Point2D(0.0, -length)

        # Outline (closed polygon)
        outline = (
            p_top_left,
            p_shoulder,
            p_armhole_top,
            p_armhole_mid,
            p_side_bottom,
            p_bottom_left,
            p_top_left,  # close
        )

        # Bust dart
        bust_dart_apex = Point2D(width * 0.6, -(length * 0.4))
        bust_dart_angle = max(5.0, (chest - waist) / chest * 30.0)
        bust_dart_length = bust_ease * 2.0

        # Waist dart (smaller shaping dart)
        waist_dart_apex = Point2D(width * 0.35, -(length * 0.85))
        waist_dart_angle = max(3.0, (chest - waist) / chest * 15.0)
        waist_dart_length = bust_ease * 1.2

        darts = (
            DartGeometry(apex=bust_dart_apex, angle=bust_dart_angle, length=bust_dart_length),
            DartGeometry(apex=waist_dart_apex, angle=waist_dart_angle, length=waist_dart_length),
        )

        # Seam lines along edges
        seam_lines = (
            Line2D(start=p_top_left, end=p_shoulder),          # shoulder seam
            Line2D(start=p_armhole_top, end=p_armhole_mid),    # armhole
            Line2D(start=p_side_bottom, end=p_bottom_left),    # hem
            Line2D(start=p_bottom_left, end=p_top_left),       # center front
        )

        # Grain line: vertical center of piece
        grain_x = width / 2.0
        grain_line = Line2D(
            start=Point2D(grain_x, -(length * 0.1)),
            end=Point2D(grain_x, -(length * 0.9)),
        )

        # Notch marks at key construction points
        notch_marks = (
            p_shoulder,       # shoulder notch
            p_armhole_mid,    # armhole notch
            Point2D(0.0, -length),  # waist center front
        )

        return PatternPiece(
            piece_id="front_bodice",
            label="Front Bodice",
            outline=outline,
            seam_lines=seam_lines,
            darts=darts,
            grain_line=grain_line,
            notch_marks=notch_marks,
            seam_allowance=DEFAULT_SEAM_ALLOWANCE,
        )

    # ------------------------------------------------------------------
    # Back bodice drafting (simplified Parsons)
    # ------------------------------------------------------------------

    @staticmethod
    def _draft_back(
        profile: MeasurementProfile,
        bust_ease: float,
        waist_ease: float,
    ) -> PatternPiece:
        chest = profile.chest
        waist = profile.waist
        shoulder_width = profile.shoulder_width
        torso_length = profile.torso_length

        # Back is slightly narrower than front
        width = chest / 4.0 + bust_ease / 2.0 - 1.0
        length = torso_length

        shoulder_half = shoulder_width / 2.0
        shoulder_drop = 3.0

        p_top_left = Point2D(0.0, 0.0)
        p_shoulder = Point2D(shoulder_half, -shoulder_drop)
        p_armhole_top = Point2D(width, -shoulder_drop - 2.0)
        p_armhole_mid = Point2D(width, -(length * 0.4))
        p_side_bottom = Point2D(width, -length)
        p_bottom_left = Point2D(0.0, -length)

        outline = (
            p_top_left,
            p_shoulder,
            p_armhole_top,
            p_armhole_mid,
            p_side_bottom,
            p_bottom_left,
            p_top_left,  # close
        )

        # Shoulder dart (back uses shoulder dart instead of bust dart)
        shoulder_dart_apex = Point2D(shoulder_half * 0.5, -(shoulder_drop + 2.0))
        shoulder_dart_angle = max(4.0, (chest - waist) / chest * 12.0)
        shoulder_dart_length = bust_ease * 1.5

        darts = (
            DartGeometry(
                apex=shoulder_dart_apex,
                angle=shoulder_dart_angle,
                length=shoulder_dart_length,
            ),
        )

        seam_lines = (
            Line2D(start=p_top_left, end=p_shoulder),          # shoulder seam
            Line2D(start=p_armhole_top, end=p_armhole_mid),    # armhole
            Line2D(start=p_side_bottom, end=p_bottom_left),    # hem
            Line2D(start=p_bottom_left, end=p_top_left),       # center back
        )

        grain_x = width / 2.0
        grain_line = Line2D(
            start=Point2D(grain_x, -(length * 0.1)),
            end=Point2D(grain_x, -(length * 0.9)),
        )

        notch_marks = (
            p_shoulder,
            p_armhole_mid,
            Point2D(0.0, -length),
        )

        return PatternPiece(
            piece_id="back_bodice",
            label="Back Bodice",
            outline=outline,
            seam_lines=seam_lines,
            darts=darts,
            grain_line=grain_line,
            notch_marks=notch_marks,
            seam_allowance=DEFAULT_SEAM_ALLOWANCE,
        )

    # ------------------------------------------------------------------
    # Correction application
    # ------------------------------------------------------------------

    def apply_corrections(
        self,
        sloper: BodiceSloper,
        corrections: list[CorrectionStrategy],
    ) -> BodiceSloper:
        """Apply geometry corrections and return a new BodiceSloper.

        The original sloper is not mutated (frozen dataclass).
        Each correction's magnitude is scaled by its dampening_factor.
        """
        front = sloper.front_bodice
        back = sloper.back_bodice
        bust_ease = sloper.bust_ease
        waist_ease = sloper.waist_ease

        for correction in corrections:
            effective = correction.magnitude * correction.dampening_factor

            if correction.correction_type == CorrectionType.ADJUST_DART_PLACEMENT:
                front, back = self._shift_dart_apex(front, back, effective)

            elif correction.correction_type == CorrectionType.ADJUST_DART_ANGLE:
                front, back = self._adjust_dart_angle(front, back, effective)

            elif correction.correction_type == CorrectionType.ADJUST_DART_LENGTH:
                front, back = self._adjust_dart_length(front, back, effective)

            elif correction.correction_type == CorrectionType.REDISTRIBUTE_EASE:
                bust_ease += effective
                waist_ease += effective * 0.6  # waist gets less redistribution

        new_sloper = BodiceSloper(
            sloper_id=str(uuid.uuid4()),
            profile=sloper.profile,
            front_bodice=front,
            back_bodice=back,
            bust_ease=bust_ease,
            waist_ease=waist_ease,
            metadata={
                **sloper.metadata,
                "corrected_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Validate resulting geometry
        errors = self.validate_geometry(new_sloper)
        if errors:
            raise ValueError(
                f"Corrections produced invalid geometry: {'; '.join(errors)}"
            )

        return new_sloper

    # ------------------------------------------------------------------
    # Geometry validation
    # ------------------------------------------------------------------

    def validate_geometry(self, sloper: BodiceSloper) -> list[str]:
        """Check sloper geometry and return a list of error strings."""
        errors: list[str] = []
        for piece in (sloper.front_bodice, sloper.back_bodice):
            label = piece.label
            # Closed outline
            if len(piece.outline) < 2 or piece.outline[0] != piece.outline[-1]:
                errors.append(f"{label}: outline is not closed")
            # At least one dart
            if len(piece.darts) < 1:
                errors.append(f"{label}: must have at least one dart")
            # Positive seam allowance
            if piece.seam_allowance <= 0:
                errors.append(f"{label}: seam_allowance must be > 0")
            # Grain line exists (non-degenerate)
            gl = piece.grain_line
            if gl.start == gl.end:
                errors.append(f"{label}: grain_line is degenerate (zero length)")
            # At least one notch mark
            if len(piece.notch_marks) < 1:
                errors.append(f"{label}: must have at least one notch mark")
        return errors

    # ------------------------------------------------------------------
    # Internal helpers for correction application
    # ------------------------------------------------------------------

    @staticmethod
    def _shift_dart_apex(
        front: PatternPiece, back: PatternPiece, shift: float
    ) -> tuple[PatternPiece, PatternPiece]:
        """Shift dart apex positions by *shift* cm in the x-direction."""
        new_front_darts = tuple(
            DartGeometry(
                apex=Point2D(d.apex.x + shift, d.apex.y),
                angle=d.angle,
                length=d.length,
            )
            for d in front.darts
        )
        new_back_darts = tuple(
            DartGeometry(
                apex=Point2D(d.apex.x + shift, d.apex.y),
                angle=d.angle,
                length=d.length,
            )
            for d in back.darts
        )
        return (
            dataclasses.replace(front, darts=new_front_darts),
            dataclasses.replace(back, darts=new_back_darts),
        )

    @staticmethod
    def _adjust_dart_angle(
        front: PatternPiece, back: PatternPiece, delta_degrees: float
    ) -> tuple[PatternPiece, PatternPiece]:
        """Change dart angles by *delta_degrees*."""
        new_front_darts = tuple(
            DartGeometry(apex=d.apex, angle=d.angle + delta_degrees, length=d.length)
            for d in front.darts
        )
        new_back_darts = tuple(
            DartGeometry(apex=d.apex, angle=d.angle + delta_degrees, length=d.length)
            for d in back.darts
        )
        return (
            dataclasses.replace(front, darts=new_front_darts),
            dataclasses.replace(back, darts=new_back_darts),
        )

    @staticmethod
    def _adjust_dart_length(
        front: PatternPiece, back: PatternPiece, delta_cm: float
    ) -> tuple[PatternPiece, PatternPiece]:
        """Change dart lengths by *delta_cm*."""
        new_front_darts = tuple(
            DartGeometry(apex=d.apex, angle=d.angle, length=d.length + delta_cm)
            for d in front.darts
        )
        new_back_darts = tuple(
            DartGeometry(apex=d.apex, angle=d.angle, length=d.length + delta_cm)
            for d in back.darts
        )
        return (
            dataclasses.replace(front, darts=new_front_darts),
            dataclasses.replace(back, darts=new_back_darts),
        )
