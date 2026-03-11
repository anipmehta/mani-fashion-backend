"""Property-based tests for shared data models.

Tests for MeasurementProfile validation (Property 3) and
TensionThresholds validation (Property 16).
"""

from __future__ import annotations

import dataclasses

from hypothesis import given, settings, strategies as st
from hypothesis.strategies import composite

from agentic_pattern_engine.models import MeasurementProfile, TensionThresholds
from tests.conftest import (
    invalid_measurement_profiles,
    measurement_profiles,
)


# ---------------------------------------------------------------------------
# Property 3: Invalid measurement rejection
# Feature: agentic-pattern-engine, Property 3: Invalid measurement rejection
# Validates: Requirements 1.4
# ---------------------------------------------------------------------------

@given(profile=invalid_measurement_profiles())
@settings(max_examples=100)
def test_invalid_measurement_rejection(profile: MeasurementProfile) -> None:
    """For any MeasurementProfile with at least one field outside anatomical
    range, validate() must return a non-empty error list identifying the
    invalid fields."""
    errors = profile.validate()
    assert len(errors) > 0, (
        f"Expected validation errors for profile {profile}, got none"
    )
    # Each error should reference a field name
    all_fields = set(MeasurementProfile.RANGES.fget(None) if False else {  # type: ignore
        "chest", "waist", "hip", "shoulder_width", "torso_length",
    })
    for err in errors:
        assert any(f in err for f in all_fields), (
            f"Error '{err}' does not reference a known field"
        )


@given(profile=measurement_profiles())
@settings(max_examples=100)
def test_valid_measurement_acceptance(profile: MeasurementProfile) -> None:
    """For any valid MeasurementProfile, validate() must return an empty
    error list."""
    errors = profile.validate()
    assert errors == [], (
        f"Expected no validation errors for valid profile {profile}, got {errors}"
    )


# ---------------------------------------------------------------------------
# Property 16: Invalid threshold rejection
# Feature: agentic-pattern-engine, Property 16: Invalid threshold rejection
# Validates: Requirements 8.4
# ---------------------------------------------------------------------------

@composite
def _invalid_tension_thresholds(draw: st.DrawFn) -> TensionThresholds:
    """Generate TensionThresholds with at least one zero or negative value."""
    field_name = draw(st.sampled_from([
        "bust", "waist", "shoulder", "armhole",
        "side_seam", "center_front", "center_back",
    ]))
    # Start with valid defaults, then set one field to zero or negative
    invalid_value = draw(st.floats(max_value=0.0, allow_nan=False, allow_infinity=False))
    return dataclasses.replace(TensionThresholds(), **{field_name: invalid_value})


@given(thresholds=_invalid_tension_thresholds())
@settings(max_examples=100)
def test_invalid_threshold_rejection(thresholds: TensionThresholds) -> None:
    """For any TensionThresholds with zero or negative values, validate()
    must return a non-empty error list."""
    errors = thresholds.validate()
    assert len(errors) > 0, (
        f"Expected validation errors for thresholds {thresholds}, got none"
    )
