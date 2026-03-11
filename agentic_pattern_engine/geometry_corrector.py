"""Geometry Corrector — dart/ease adjustments for fit issues.

Plans and validates corrections to a BodiceSloper based on detected
FitIssues. Corrections are priority-ordered: excess_tension first,
then pulling, then insufficient_tension.
"""

from __future__ import annotations

import dataclasses

from agentic_pattern_engine.models import (
    BodiceSloper,
    CorrectionStrategy,
    CorrectionType,
    DartGeometry,
    FitIssue,
    FitIssueType,
    FitRegion,
    MeasurementProfile,
    PatternPiece,
    Point2D,
)

# Priority ordering for issue types (lower = higher priority)
_PRIORITY = {
    FitIssueType.EXCESS_TENSION: 0,
    FitIssueType.PULLING: 1,
    FitIssueType.INSUFFICIENT_TENSION: 2,
}

# Correction mapping: (issue_type, region) -> correction_type
_CORRECTION_MAP: dict[FitIssueType, CorrectionType] = {
    FitIssueType.EXCESS_TENSION: CorrectionType.ADJUST_DART_ANGLE,
    FitIssueType.INSUFFICIENT_TENSION: CorrectionType.ADJUST_DART_LENGTH,
    FitIssueType.PULLING: CorrectionType.ADJUST_DART_PLACEMENT,
}

# Regions that benefit from ease redistribution
_EASE_REGIONS = {FitRegion.BUST, FitRegion.WAIST, FitRegion.SIDE_SEAM}


class DartEaseGeometryCorrector:
    """Plan and validate geometry corrections for detected fit issues."""

    def plan_corrections(
        self,
        fit_issues: list[FitIssue],
        current_sloper: BodiceSloper,
        profile: MeasurementProfile,
        dampening_factor: float = 1.0,
    ) -> list[CorrectionStrategy]:
        """Plan corrections for detected fit issues.

        Priority: excess_tension > pulling > insufficient_tension.
        Returns at least one CorrectionStrategy per FitIssue.
        """
        if not fit_issues:
            return []

        # Sort by priority
        sorted_issues = sorted(fit_issues, key=lambda i: _PRIORITY[i.issue_type])

        corrections: list[CorrectionStrategy] = []
        for issue in sorted_issues:
            correction_type = _CORRECTION_MAP[issue.issue_type]

            # Compute magnitude based on violation
            magnitude = self._compute_magnitude(issue, current_sloper)

            corrections.append(CorrectionStrategy(
                target_region=issue.region,
                issue_type=issue.issue_type,
                correction_type=correction_type,
                magnitude=magnitude * dampening_factor,
                dampening_factor=dampening_factor,
            ))

            # For ease-related regions, also add ease redistribution
            if issue.region in _EASE_REGIONS and issue.issue_type == FitIssueType.EXCESS_TENSION:
                ease_mag = min(issue.violation_magnitude * 0.002, 1.0)  # cm
                corrections.append(CorrectionStrategy(
                    target_region=issue.region,
                    issue_type=issue.issue_type,
                    correction_type=CorrectionType.REDISTRIBUTE_EASE,
                    magnitude=ease_mag * dampening_factor,
                    dampening_factor=dampening_factor,
                ))

        return corrections

    def validate_corrections(
        self,
        corrections: list[CorrectionStrategy],
        current_sloper: BodiceSloper,
        profile: MeasurementProfile,
        max_ease_tolerance: float = 2.0,
    ) -> list[str]:
        """Validate corrections won't violate max ease tolerance."""
        errors: list[str] = []

        # Sum up ease changes from redistribute_ease corrections
        total_bust_ease_change = 0.0
        total_waist_ease_change = 0.0
        for c in corrections:
            if c.correction_type == CorrectionType.REDISTRIBUTE_EASE:
                if c.target_region in (FitRegion.BUST, FitRegion.SIDE_SEAM):
                    total_bust_ease_change += c.magnitude
                elif c.target_region == FitRegion.WAIST:
                    total_waist_ease_change += c.magnitude

        new_bust_ease = current_sloper.bust_ease + total_bust_ease_change
        new_waist_ease = current_sloper.waist_ease + total_waist_ease_change

        if abs(new_bust_ease - current_sloper.bust_ease) > max_ease_tolerance:
            errors.append(
                f"Bust ease change {total_bust_ease_change:.2f}cm exceeds "
                f"max tolerance {max_ease_tolerance}cm"
            )
        if abs(new_waist_ease - current_sloper.waist_ease) > max_ease_tolerance:
            errors.append(
                f"Waist ease change {total_waist_ease_change:.2f}cm exceeds "
                f"max tolerance {max_ease_tolerance}cm"
            )

        # Validate dart angle corrections don't go negative
        for c in corrections:
            if c.correction_type in (
                CorrectionType.ADJUST_DART_ANGLE,
                CorrectionType.ADJUST_DART_LENGTH,
            ):
                if c.magnitude < 0:
                    errors.append(
                        f"Negative correction magnitude {c.magnitude} "
                        f"for {c.target_region.value}"
                    )

        return errors

    @staticmethod
    def _compute_magnitude(issue: FitIssue, sloper: BodiceSloper) -> float:
        """Compute correction magnitude from violation magnitude."""
        violation = issue.violation_magnitude

        if issue.issue_type == FitIssueType.EXCESS_TENSION:
            # Increase dart angle proportional to violation
            # Scale: 100 Pa violation -> ~2 degrees adjustment
            return min(violation * 0.02, 15.0)

        if issue.issue_type == FitIssueType.INSUFFICIENT_TENSION:
            # Decrease dart length proportional to violation
            return min(violation * 0.01, 5.0)

        if issue.issue_type == FitIssueType.PULLING:
            # Adjust dart placement proportional to violation
            return min(violation * 0.015, 3.0)

        return 0.0

    def apply_to_sloper(
        self,
        sloper: BodiceSloper,
        corrections: list[CorrectionStrategy],
    ) -> BodiceSloper:
        """Apply corrections to a sloper and return updated copy.

        Modifies dart geometry and ease values based on corrections.
        """
        new_bust_ease = sloper.bust_ease
        new_waist_ease = sloper.waist_ease
        front_darts = list(sloper.front_bodice.darts)
        back_darts = list(sloper.back_bodice.darts)

        for c in corrections:
            if c.correction_type == CorrectionType.REDISTRIBUTE_EASE:
                if c.target_region in (FitRegion.BUST, FitRegion.SIDE_SEAM):
                    new_bust_ease += c.magnitude
                elif c.target_region == FitRegion.WAIST:
                    new_waist_ease += c.magnitude

            elif c.correction_type == CorrectionType.ADJUST_DART_ANGLE:
                # Widen dart angle on front piece for bust/waist regions
                target_darts = front_darts if c.target_region in (
                    FitRegion.BUST, FitRegion.WAIST, FitRegion.CENTER_FRONT,
                    FitRegion.ARMHOLE, FitRegion.SIDE_SEAM,
                ) else back_darts
                if target_darts:
                    d = target_darts[0]
                    target_darts[0] = DartGeometry(
                        apex=d.apex,
                        angle=d.angle + c.magnitude,
                        length=d.length,
                    )

            elif c.correction_type == CorrectionType.ADJUST_DART_LENGTH:
                target_darts = front_darts if c.target_region in (
                    FitRegion.BUST, FitRegion.WAIST, FitRegion.CENTER_FRONT,
                    FitRegion.ARMHOLE, FitRegion.SIDE_SEAM,
                ) else back_darts
                if target_darts:
                    d = target_darts[0]
                    target_darts[0] = DartGeometry(
                        apex=d.apex,
                        angle=d.angle,
                        length=max(0.5, d.length - c.magnitude),
                    )

            elif c.correction_type == CorrectionType.ADJUST_DART_PLACEMENT:
                target_darts = front_darts if c.target_region in (
                    FitRegion.BUST, FitRegion.WAIST, FitRegion.CENTER_FRONT,
                    FitRegion.ARMHOLE, FitRegion.SIDE_SEAM,
                ) else back_darts
                if target_darts:
                    d = target_darts[0]
                    target_darts[0] = DartGeometry(
                        apex=Point2D(d.apex.x + c.magnitude * 0.1, d.apex.y),
                        angle=d.angle,
                        length=d.length,
                    )

        new_front = dataclasses.replace(
            sloper.front_bodice, darts=tuple(front_darts)
        )
        new_back = dataclasses.replace(
            sloper.back_bodice, darts=tuple(back_darts)
        )
        return dataclasses.replace(
            sloper,
            front_bodice=new_front,
            back_bodice=new_back,
            bust_ease=new_bust_ease,
            waist_ease=new_waist_ease,
        )
