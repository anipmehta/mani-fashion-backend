"""Grading Engine — re-grade parsed patterns to new body measurements.

Computes per-dimension measurement deltas between source and target
profiles, applies proportional scaling to pattern pieces, and
optionally runs the self-correction engine for fit refinement.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from agentic_pattern_engine.models import (
    DartGeometry,
    GradingResult,
    Line2D,
    MeasurementProfile,
    PatternPiece,
    Point2D,
)

if TYPE_CHECKING:
    from agentic_pattern_engine.agent_orchestrator import AgentOrchestrator

# Threshold for emitting large-delta warning (cm)
LARGE_DELTA_THRESHOLD = 15.0

# Measurement fields shared between profiles for delta computation
_BODICE_FIELDS = ("chest", "waist", "hip", "shoulder_width", "torso_length")
_SKIRT_FIELDS = ("waist", "hip", "hip_depth", "desired_length")


class GradingEngine:
    """Re-grade parsed patterns to new body measurements."""

    def __init__(
        self,
        orchestrator: AgentOrchestrator | None = None,
    ) -> None:
        self._orchestrator = orchestrator

    def grade(
        self,
        pieces: list[PatternPiece],
        source_profile: MeasurementProfile,
        target_profile: MeasurementProfile,
        garment_type: str,
    ) -> GradingResult:
        """Compute deltas, scale proportionally, optionally self-correct.

        Args:
            pieces: Parsed pattern pieces from source pattern.
            source_profile: Body measurements of the source pattern.
            target_profile: Target body measurements to grade to.
            garment_type: "bodice" or "skirt".

        Returns:
            GradingResult with original pieces, graded pieces, deltas,
            optional run_result from self-correction, and warnings.
        """
        warnings: list[str] = []

        # Compute deltas
        deltas = self._compute_deltas(
            source_profile, target_profile, garment_type,
        )

        # Check for large deltas
        for field, delta in deltas.items():
            if abs(delta) > LARGE_DELTA_THRESHOLD:
                warnings.append(
                    f"Large grade jump for {field}: "
                    f"{delta:+.1f} cm (> {LARGE_DELTA_THRESHOLD} cm). "
                    f"Results may require manual review."
                )

        # Apply proportional scaling
        scaled_pieces = self._apply_proportional_scaling(
            pieces, deltas, source_profile, garment_type,
        )

        # Optionally run self-correction
        run_result = None
        if self._orchestrator is not None:
            run_result = self._run_self_correction(
                scaled_pieces, target_profile, garment_type,
            )
            if (
                run_result is not None
                and run_result.final_pieces is not None
            ):
                scaled_pieces = run_result.final_pieces

        return GradingResult(
            original_pieces=list(pieces),
            graded_pieces=scaled_pieces,
            deltas=deltas,
            run_result=run_result,
            warnings=warnings,
        )

    def _compute_deltas(
        self,
        source_profile: MeasurementProfile,
        target_profile: MeasurementProfile,
        garment_type: str,
    ) -> dict[str, float]:
        """Compute target - source for every shared measurement field."""
        fields = (
            _SKIRT_FIELDS if garment_type == "skirt" else _BODICE_FIELDS
        )
        deltas: dict[str, float] = {}
        for field in fields:
            src_val = getattr(source_profile, field, None)
            tgt_val = getattr(target_profile, field, None)
            if src_val is not None and tgt_val is not None:
                deltas[field] = tgt_val - src_val
        return deltas

    def _apply_proportional_scaling(
        self,
        pieces: list[PatternPiece],
        deltas: dict[str, float],
        source_profile: MeasurementProfile,
        garment_type: str,
    ) -> list[PatternPiece]:
        """Scale pattern piece outlines proportionally.

        Computes horizontal and vertical scale factors from measurement
        ratios. Preserves seam allowance values. Scales dart positions
        proportionally.
        """
        # Compute scale factors from circumference and length ratios
        h_ratio, v_ratio = self._compute_scale_ratios(
            deltas, source_profile, garment_type,
        )

        scaled: list[PatternPiece] = []
        for piece in pieces:
            new_outline = tuple(
                Point2D(p.x * h_ratio, p.y * v_ratio)
                for p in piece.outline
            )
            new_seam_lines = tuple(
                Line2D(
                    start=Point2D(
                        sl.start.x * h_ratio, sl.start.y * v_ratio,
                    ),
                    end=Point2D(
                        sl.end.x * h_ratio, sl.end.y * v_ratio,
                    ),
                )
                for sl in piece.seam_lines
            )
            new_darts = tuple(
                DartGeometry(
                    apex=Point2D(
                        d.apex.x * h_ratio, d.apex.y * v_ratio,
                    ),
                    angle=d.angle,   # preserve dart angle
                    length=d.length * v_ratio,
                )
                for d in piece.darts
            )
            new_grain = Line2D(
                start=Point2D(
                    piece.grain_line.start.x * h_ratio,
                    piece.grain_line.start.y * v_ratio,
                ),
                end=Point2D(
                    piece.grain_line.end.x * h_ratio,
                    piece.grain_line.end.y * v_ratio,
                ),
            )
            new_notches = tuple(
                Point2D(n.x * h_ratio, n.y * v_ratio)
                for n in piece.notch_marks
            )

            scaled.append(dataclasses.replace(
                piece,
                outline=new_outline,
                seam_lines=new_seam_lines,
                darts=new_darts,
                grain_line=new_grain,
                notch_marks=new_notches,
                # seam_allowance preserved — not scaled
            ))
        return scaled

    @staticmethod
    def _compute_scale_ratios(
        deltas: dict[str, float],
        source_profile: MeasurementProfile,
        garment_type: str,
    ) -> tuple[float, float]:
        """Compute horizontal and vertical scale ratios.

        Horizontal ratio is based on circumference fields (hip, waist,
        chest). Vertical ratio is based on length fields (torso_length,
        desired_length).
        """
        if garment_type == "skirt":
            h_field = "hip"
            v_field = "desired_length"
        else:
            h_field = "chest"
            v_field = "torso_length"

        src_h = getattr(source_profile, h_field, None) or 1.0
        src_v = getattr(source_profile, v_field, None) or 1.0

        h_delta = deltas.get(h_field, 0.0)
        v_delta = deltas.get(v_field, 0.0)

        h_ratio = (src_h + h_delta) / src_h
        v_ratio = (src_v + v_delta) / src_v

        return h_ratio, v_ratio

    def _run_self_correction(
        self,
        pieces: list[PatternPiece],
        target_profile: MeasurementProfile,
        garment_type: str,
    ) -> "AgentRunResult | None":
        """Run self-correction on scaled pieces via orchestrator."""
        from agentic_pattern_engine.models import AgentRunResult

        if self._orchestrator is None:
            return None

        try:
            result = self._orchestrator.run(target_profile)
            return result
        except Exception:
            return None
