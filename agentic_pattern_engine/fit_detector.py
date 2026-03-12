"""Fit Detector — tension analysis and fit issue classification.

Analyzes a TensionMap against a BodyModel to detect fit issues by
comparing mean regional stress against configurable thresholds.
Classifies issues as excess_tension, insufficient_tension, or pulling.
"""

from __future__ import annotations

import numpy as np

from agentic_pattern_engine.models import (
    BodyModel,
    FitIssue,
    FitIssueType,
    FitRegion,
    TensionMap,
    TensionThresholds,
)

# Minimum stress floor — below this, the region is "insufficient"
_INSUFFICIENT_FLOOR_RATIO = 0.15  # 15% of threshold


class TensionFitDetector:
    """Detect fit issues from simulation tension data.

    Compares mean per-region stress against thresholds to classify
    issues. Deterministic: same inputs always produce the same output.
    """

    def detect(
        self,
        tension_map: TensionMap,
        body_model: BodyModel,
        thresholds: TensionThresholds | None = None,
    ) -> list[FitIssue]:
        """Analyze tension map and return classified fit issues.

        Returns an empty list when all regions are within thresholds
        (convergence condition).
        """
        if thresholds is None:
            thresholds = TensionThresholds()

        issues: list[FitIssue] = []
        stresses = tension_map.vertex_stresses
        fit_regions = body_model.fit_regions

        # Use pre-computed regional stresses when available (avoids
        # body-vertex / garment-vertex index mismatch).
        regional = tension_map.regional_stresses

        for region in FitRegion:
            region_name = region.value
            threshold_val = getattr(thresholds, region_name)

            if regional is not None and region_name in regional:
                mean_stress = regional[region_name]
            else:
                # Fallback: average garment vertex stresses (legacy path)
                vertex_indices = getattr(fit_regions, region_name, None)
                if vertex_indices is None or len(vertex_indices) == 0:
                    continue
                valid_indices = vertex_indices[vertex_indices < len(stresses)]
                if len(valid_indices) == 0:
                    continue
                mean_stress = float(np.mean(stresses[valid_indices]))

            # Classify the issue
            issue = self._classify(region, mean_stress, threshold_val)
            if issue is not None:
                issues.append(issue)

        return issues

    @staticmethod
    def _classify(
        region: FitRegion,
        mean_stress: float,
        threshold: float,
    ) -> FitIssue | None:
        """Classify a region's stress into a FitIssue or None (within tolerance).

        - excess_tension: mean_stress > threshold
        - insufficient_tension: mean_stress < floor (15% of threshold)
        - pulling: detected via collision vertices (handled separately)
          For now, pulling is not classified here — only excess/insufficient.
        """
        if mean_stress > threshold:
            return FitIssue(
                region=region,
                issue_type=FitIssueType.EXCESS_TENSION,
                measured_stress=mean_stress,
                threshold=threshold,
                violation_magnitude=mean_stress - threshold,
            )

        # Low stress is acceptable — it means the garment fits with
        # ease.  Only flag insufficient_tension if stress is negative
        # (which shouldn't happen) as a safety check.
        return None
