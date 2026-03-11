"""Property-based tests for the ParametricBodyModelBuilder.

Tests Properties 4 and 5 from the Agentic Pattern Engine design document.
"""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings

from agentic_pattern_engine.body_model_builder import ParametricBodyModelBuilder
from agentic_pattern_engine.models import MeasurementProfile
from tests.conftest import measurement_profiles


# Feature: agentic-pattern-engine, Property 4: Body model measurement round-trip
# **Validates: Requirements 2.1, 2.2, 2.5**
@given(profile=measurement_profiles())
@settings(max_examples=100)
def test_body_model_round_trip(profile: MeasurementProfile) -> None:
    """For any valid MeasurementProfile, extract_measurements(build(p)) must
    match the original within 3mm per dimension, and all 7 FitRegion vertex
    groups must be non-empty."""
    builder = ParametricBodyModelBuilder()
    body_model = builder.build(profile)
    extracted = builder.extract_measurements(body_model)

    # Within 3mm (0.3 cm) tolerance
    assert abs(extracted.chest - profile.chest) <= 0.3, (
        f"chest: {extracted.chest} vs {profile.chest}"
    )
    assert abs(extracted.waist - profile.waist) <= 0.3, (
        f"waist: {extracted.waist} vs {profile.waist}"
    )
    assert abs(extracted.hip - profile.hip) <= 0.3, (
        f"hip: {extracted.hip} vs {profile.hip}"
    )
    assert abs(extracted.shoulder_width - profile.shoulder_width) <= 0.3, (
        f"shoulder_width: {extracted.shoulder_width} vs {profile.shoulder_width}"
    )
    assert abs(extracted.torso_length - profile.torso_length) <= 0.3, (
        f"torso_length: {extracted.torso_length} vs {profile.torso_length}"
    )

    # All fit regions non-empty
    for region_name in [
        "bust", "waist", "shoulder", "armhole",
        "side_seam", "center_front", "center_back",
    ]:
        region_verts = getattr(body_model.fit_regions, region_name)
        assert len(region_verts) > 0, f"fit region '{region_name}' is empty"


# Feature: agentic-pattern-engine, Property 5: Body model determinism
# **Validates: Requirements 2.4**
@given(profile=measurement_profiles())
@settings(max_examples=100)
def test_body_model_determinism(profile: MeasurementProfile) -> None:
    """For any valid MeasurementProfile, build(p) called twice must produce
    identical BodyModels (same vertices, faces, SMPL params)."""
    builder = ParametricBodyModelBuilder()
    m1 = builder.build(profile)
    m2 = builder.build(profile)

    np.testing.assert_array_equal(m1.vertices, m2.vertices)
    np.testing.assert_array_equal(m1.faces, m2.faces)
    np.testing.assert_array_equal(m1.smpl_shape_params, m2.smpl_shape_params)
