"""Property tests for the Fit Detector.

Properties 8 and 15 from the design document.
"""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite

from agentic_pattern_engine.body_model_builder import ParametricBodyModelBuilder
from agentic_pattern_engine.fit_detector import TensionFitDetector
from agentic_pattern_engine.models import (
    FitIssueType,
    FitRegion,
    TensionMap,
    TensionThresholds,
)
from tests.conftest import measurement_profiles, tension_thresholds

_detector = TensionFitDetector()
_builder = ParametricBodyModelBuilder()

# All region names in order
_REGION_NAMES = [r.value for r in FitRegion]


@composite
def _body_model_and_tension(draw):
    """Generate a body model and a tension map with matching vertex count."""
    profile = draw(measurement_profiles())
    body = _builder.build(profile)
    n_verts = len(body.vertices)
    # Generate per-vertex stresses (non-negative)
    stresses = np.array(
        [draw(st.floats(min_value=0.0, max_value=3000.0,
                        allow_nan=False, allow_infinity=False))
         for _ in range(n_verts)],
        dtype=np.float64,
    )
    tm = TensionMap(
        vertex_stresses=stresses,
        collision_vertices=np.array([], dtype=np.int32),
    )
    return body, tm


# Feature: agentic-pattern-engine, Property 8: Fit detection correctness
@given(data=_body_model_and_tension(), thresholds=tension_thresholds())
@settings(max_examples=50)
def test_fit_detection_correctness(data, thresholds: TensionThresholds):
    """For any TensionMap, BodyModel, and TensionThresholds:
    - every region exceeding threshold must appear in issues
    - no region within threshold should appear (unless insufficient)
    - deterministic output
    """
    body, tm = data
    issues = _detector.detect(tm, body, thresholds)

    # Build expected: compute mean stress per region
    stresses = tm.vertex_stresses
    for region in FitRegion:
        indices = getattr(body.fit_regions, region.value)
        valid = indices[indices < len(stresses)]
        if len(valid) == 0:
            continue
        mean_stress = float(np.mean(stresses[valid]))
        threshold_val = getattr(thresholds, region.value)

        matching = [i for i in issues if i.region == region]

        if mean_stress > threshold_val:
            # Must appear as excess_tension
            assert len(matching) == 1, f"{region} should have excess_tension issue"
            assert matching[0].issue_type == FitIssueType.EXCESS_TENSION
            assert abs(matching[0].measured_stress - mean_stress) < 1e-6
            assert abs(matching[0].threshold - threshold_val) < 1e-6
        else:
            # At or below threshold — should NOT appear
            assert len(matching) == 0, f"{region} should not have issues"

    # Determinism: second call must produce identical results
    issues2 = _detector.detect(tm, body, thresholds)
    assert len(issues) == len(issues2)
    for a, b in zip(issues, issues2):
        assert a == b


# Feature: agentic-pattern-engine, Property 15: Custom threshold usage
@given(data=_body_model_and_tension(), thresholds=tension_thresholds())
@settings(max_examples=50)
def test_custom_threshold_usage(data, thresholds: TensionThresholds):
    """For any valid custom TensionThresholds, FitIssue.threshold must
    equal the custom value for that region."""
    body, tm = data
    issues = _detector.detect(tm, body, thresholds)

    for issue in issues:
        expected_threshold = getattr(thresholds, issue.region.value)
        assert issue.threshold == expected_threshold, (
            f"Issue for {issue.region} has threshold {issue.threshold}, "
            f"expected custom threshold {expected_threshold}"
        )
