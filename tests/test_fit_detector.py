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


# ---------------------------------------------------------------------------
# PR 3: spec_regions / spec_thresholds filtering tests
# ---------------------------------------------------------------------------

from tests.conftest import SAMPLE_PROFILES

from agentic_pattern_engine.garment_spec import BodiceGarmentSpec

# Test constants
_BUST = FitRegion.BUST.value
_WAIST = FitRegion.WAIST.value
_SHOULDER = FitRegion.SHOULDER.value
_ARMHOLE = FitRegion.ARMHOLE.value
_HIGH_STRESS = 999.0
_BUST_THRESHOLD = BodiceGarmentSpec.DEFAULT_TENSION_THRESHOLDS[_BUST]
_WAIST_THRESHOLD = BodiceGarmentSpec.DEFAULT_TENSION_THRESHOLDS[_WAIST]


def test_fit_detector_spec_regions_filters_to_subset() -> None:
    """When spec_regions is provided, only those regions are evaluated."""
    profile = SAMPLE_PROFILES["medium"]
    body = _builder.build(profile)

    regional = {r.value: _HIGH_STRESS for r in FitRegion}
    tm = TensionMap(
        vertex_stresses=np.zeros(len(body.vertices)),
        collision_vertices=np.array([], dtype=np.int32),
        regional_stresses=regional,
    )

    issues = _detector.detect(
        tm, body,
        spec_regions=[_BUST, _WAIST],
        spec_thresholds={
            _BUST: _BUST_THRESHOLD,
            _WAIST: _WAIST_THRESHOLD,
        },
    )

    region_names = {i.region.value for i in issues}
    assert _BUST in region_names
    assert _WAIST in region_names
    assert _SHOULDER not in region_names
    assert _ARMHOLE not in region_names


def test_fit_detector_spec_thresholds_used() -> None:
    """When spec_thresholds is provided, those values are used
    instead of the TensionThresholds dataclass."""
    profile = SAMPLE_PROFILES["medium"]
    body = _builder.build(profile)

    bust_stress_above = _BUST_THRESHOLD + 10.0
    waist_stress_below = _WAIST_THRESHOLD - 20.0
    regional = {_BUST: bust_stress_above, _WAIST: waist_stress_below}
    tm = TensionMap(
        vertex_stresses=np.zeros(len(body.vertices)),
        collision_vertices=np.array([], dtype=np.int32),
        regional_stresses=regional,
    )

    issues = _detector.detect(
        tm, body,
        spec_regions=[_BUST, _WAIST],
        spec_thresholds={
            _BUST: _BUST_THRESHOLD,
            _WAIST: _WAIST_THRESHOLD,
        },
    )

    bust_issues = [i for i in issues if i.region == FitRegion.BUST]
    assert len(bust_issues) == 1
    assert bust_issues[0].threshold == _BUST_THRESHOLD

    waist_issues = [i for i in issues if i.region == FitRegion.WAIST]
    assert len(waist_issues) == 0


def test_fit_detector_no_spec_regions_uses_legacy() -> None:
    """When spec_regions is None, the legacy FitRegion enum path is used."""
    profile = SAMPLE_PROFILES["medium"]
    body = _builder.build(profile)

    regional = {r.value: _HIGH_STRESS for r in FitRegion}
    tm = TensionMap(
        vertex_stresses=np.zeros(len(body.vertices)),
        collision_vertices=np.array([], dtype=np.int32),
        regional_stresses=regional,
    )

    issues = _detector.detect(tm, body)
    region_names = {i.region.value for i in issues}
    assert len(region_names) == len(FitRegion)


def test_fit_detector_spec_regions_unknown_region_skipped() -> None:
    """Unknown region names (not in FitRegion enum) are skipped
    without error."""
    profile = SAMPLE_PROFILES["medium"]
    body = _builder.build(profile)

    unknown_hip = "hip"
    unknown_hem = "hem"
    regional = {
        unknown_hip: _HIGH_STRESS,
        unknown_hem: _HIGH_STRESS,
        _BUST: _HIGH_STRESS,
    }
    tm = TensionMap(
        vertex_stresses=np.zeros(len(body.vertices)),
        collision_vertices=np.array([], dtype=np.int32),
        regional_stresses=regional,
    )

    issues = _detector.detect(
        tm, body,
        spec_regions=[unknown_hip, unknown_hem, _BUST],
        spec_thresholds={
            unknown_hip: 50.0,
            unknown_hem: 30.0,
            _BUST: _BUST_THRESHOLD,
        },
    )

    region_names = {i.region.value for i in issues}
    assert _BUST in region_names
    assert unknown_hip not in region_names
    assert unknown_hem not in region_names
