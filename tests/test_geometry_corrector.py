"""Property tests for the Geometry Corrector.

Properties 9 and 10 from the design document.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite

from agentic_pattern_engine.geometry_corrector import DartEaseGeometryCorrector, _PRIORITY
from agentic_pattern_engine.models import (
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
