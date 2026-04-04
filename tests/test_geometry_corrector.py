"""Property tests for the Geometry Corrector.

Properties 9 and 10 from the design document.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite

from agentic_pattern_engine.geometry_corrector import DartEaseGeometryCorrector, _PRIORITY
from agentic_pattern_engine.models import (
    CorrectionStrategy,
    CorrectionType,
    FitIssueType,
)
from agentic_pattern_engine.sloper_generator import ParsonsSloperGenerator
from tests.conftest import fit_issues, measurement_profiles

_corrector = DartEaseGeometryCorrector()
_generator = ParsonsSloperGenerator()


# Feature: agentic-pattern-engine, Property 9: Correction planning completeness
@given(
    issues=st.lists(fit_issues(), min_size=1, max_size=7),
    profile=measurement_profiles(),
)
@settings(max_examples=100)
def test_correction_planning_completeness(issues, profile):
    """For any non-empty FitIssues list, plan_corrections must return
    at least one CorrectionStrategy per issue with valid CorrectionType,
    priority ordered (excess > pulling > insufficient)."""
    sloper = _generator.generate(profile)
    corrections = _corrector.plan_corrections(issues, sloper, profile)

    # At least one correction per issue
    assert len(corrections) >= len(issues)

    # Every correction has a valid CorrectionType
    valid_types = set(CorrectionType)
    for c in corrections:
        assert c.correction_type in valid_types

    # Check priority ordering: all excess_tension corrections come before
    # pulling, which come before insufficient_tension
    priorities = [_PRIORITY[c.issue_type] for c in corrections]
    assert priorities == sorted(priorities), (
        f"Corrections not in priority order: {[c.issue_type for c in corrections]}"
    )


# Feature: agentic-pattern-engine, Property 10: Correction geometric validity
@given(profile=measurement_profiles())
@settings(max_examples=50)
def test_correction_geometric_validity(profile):
    """For any valid BodiceSloper and CorrectionStrategies, the updated
    sloper must pass geometry validation and stay within max_ease_tolerance."""
    sloper = _generator.generate(profile)

    # Create some synthetic issues to generate corrections
    from agentic_pattern_engine.models import FitIssue, FitIssueType, FitRegion
    issues = [
        FitIssue(
            region=FitRegion.BUST,
            issue_type=FitIssueType.EXCESS_TENSION,
            measured_stress=600.0,
            threshold=500.0,
            violation_magnitude=100.0,
        ),
    ]
    corrections = _corrector.plan_corrections(issues, sloper, profile)

    # Validate corrections
    errors = _corrector.validate_corrections(corrections, sloper, profile)
    assert errors == [], f"Validation errors: {errors}"

    # Apply corrections and verify geometry
    updated = _corrector.apply_to_sloper(sloper, corrections)

    # Updated sloper must still pass geometry validation
    geom_errors = _generator.validate_geometry(updated)
    assert geom_errors == [], f"Geometry errors after correction: {geom_errors}"

    # Ease values should be within tolerance
    assert abs(updated.bust_ease - sloper.bust_ease) <= 2.0, (
        f"Bust ease changed by {abs(updated.bust_ease - sloper.bust_ease):.2f}cm"
    )
    assert abs(updated.waist_ease - sloper.waist_ease) <= 2.0, (
        f"Waist ease changed by {abs(updated.waist_ease - sloper.waist_ease):.2f}cm"
    )


# ---------------------------------------------------------------------------
# PR 3: correction callable injection tests
# ---------------------------------------------------------------------------

from agentic_pattern_engine.models import (
    BodiceSloper,
    FitIssue,
    FitIssueType,
    FitRegion,
    MeasurementProfile,
)
from tests.conftest import SAMPLE_PROFILES


def test_geometry_corrector_plan_fn_callable_used() -> None:
    """When plan_corrections_fn is provided, it is used instead of
    the default bodice logic."""
    custom_corrections = [
        CorrectionStrategy(
            target_region=FitRegion.BUST,
            issue_type=FitIssueType.EXCESS_TENSION,
            correction_type=CorrectionType.ADJUST_DART_ANGLE,
            magnitude=5.0,
            dampening_factor=1.0,
        ),
    ]

    def fake_plan(issues, sloper, profile, df):
        return custom_corrections

    corrector = DartEaseGeometryCorrector(plan_corrections_fn=fake_plan)
    profile = SAMPLE_PROFILES["medium"]
    sloper = _generator.generate(profile)
    issues = [
        FitIssue(FitRegion.BUST, FitIssueType.EXCESS_TENSION,
                 100.0, 60.0, 40.0),
    ]

    result = corrector.plan_corrections(issues, sloper, profile)
    assert result is custom_corrections


def test_geometry_corrector_apply_fn_callable_used() -> None:
    """When apply_corrections_fn is provided, it is used instead of
    the default bodice logic."""
    profile = SAMPLE_PROFILES["medium"]
    sloper = _generator.generate(profile)
    sentinel = object()

    def fake_apply(s, corrections):
        return sentinel

    corrector = DartEaseGeometryCorrector(
        apply_corrections_fn=fake_apply,
    )
    result = corrector.apply_to_sloper(sloper, [])
    assert result is sentinel


def test_geometry_corrector_no_callables_uses_default() -> None:
    """When no callables are provided, the default bodice logic is used."""
    corrector = DartEaseGeometryCorrector()
    profile = SAMPLE_PROFILES["medium"]
    sloper = _generator.generate(profile)
    issues = [
        FitIssue(FitRegion.BUST, FitIssueType.EXCESS_TENSION,
                 100.0, 60.0, 40.0),
    ]

    corrections = corrector.plan_corrections(issues, sloper, profile)
    assert len(corrections) > 0

    updated = corrector.apply_to_sloper(sloper, corrections)
    assert updated.front_bodice is not None
    assert updated.back_bodice is not None
