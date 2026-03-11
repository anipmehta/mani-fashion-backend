"""Shared fixtures and Hypothesis strategies for the Agentic Pattern Engine."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from hypothesis import strategies as st
from hypothesis.strategies import composite

from agentic_pattern_engine.models import (
    BodiceSloper,
    CorrectionStrategy,
    CorrectionType,
    DartGeometry,
    FitIssue,
    FitIssueType,
    FitRegion,
    Line2D,
    MeasurementProfile,
    PatternPiece,
    Point2D,
    TensionMap,
    TensionThresholds,
)


# ---------------------------------------------------------------------------
# Hypothesis custom strategies
# ---------------------------------------------------------------------------

@composite
def measurement_profiles(draw: st.DrawFn) -> MeasurementProfile:
    """Generate valid MeasurementProfiles within anatomical ranges."""
    return MeasurementProfile(
        chest=draw(st.floats(min_value=60.0, max_value=180.0, allow_nan=False, allow_infinity=False)),
        waist=draw(st.floats(min_value=50.0, max_value=170.0, allow_nan=False, allow_infinity=False)),
        hip=draw(st.floats(min_value=60.0, max_value=180.0, allow_nan=False, allow_infinity=False)),
        shoulder_width=draw(st.floats(min_value=30.0, max_value=65.0, allow_nan=False, allow_infinity=False)),
        torso_length=draw(st.floats(min_value=35.0, max_value=75.0, allow_nan=False, allow_infinity=False)),
    )


@composite
def invalid_measurement_profiles(draw: st.DrawFn) -> MeasurementProfile:
    """Generate MeasurementProfiles with at least one out-of-range field."""
    field_name = draw(st.sampled_from(["chest", "waist", "hip", "shoulder_width", "torso_length"]))
    valid = draw(measurement_profiles())
    lo, hi = MeasurementProfile.RANGES.fget(None) if False else {  # type: ignore
        "chest": (60.0, 180.0),
        "waist": (50.0, 170.0),
        "hip": (60.0, 180.0),
        "shoulder_width": (30.0, 65.0),
        "torso_length": (35.0, 75.0),
    }[field_name]
    invalid_value = draw(st.one_of(
        st.floats(max_value=lo - 0.1, allow_nan=False, allow_infinity=False),
        st.floats(min_value=hi + 0.1, allow_nan=False, allow_infinity=False),
    ))
    return dataclasses.replace(valid, **{field_name: invalid_value})


@composite
def tension_thresholds(draw: st.DrawFn) -> TensionThresholds:
    """Generate valid TensionThresholds with positive values."""
    return TensionThresholds(
        bust=draw(st.floats(min_value=100.0, max_value=2000.0, allow_nan=False, allow_infinity=False)),
        waist=draw(st.floats(min_value=100.0, max_value=2000.0, allow_nan=False, allow_infinity=False)),
        shoulder=draw(st.floats(min_value=100.0, max_value=2000.0, allow_nan=False, allow_infinity=False)),
        armhole=draw(st.floats(min_value=100.0, max_value=2000.0, allow_nan=False, allow_infinity=False)),
        side_seam=draw(st.floats(min_value=100.0, max_value=2000.0, allow_nan=False, allow_infinity=False)),
        center_front=draw(st.floats(min_value=100.0, max_value=2000.0, allow_nan=False, allow_infinity=False)),
        center_back=draw(st.floats(min_value=100.0, max_value=2000.0, allow_nan=False, allow_infinity=False)),
    )


# --- Helper strategies for geometry ---

@composite
def _points(draw: st.DrawFn) -> Point2D:
    return Point2D(
        x=draw(st.floats(min_value=-200.0, max_value=200.0, allow_nan=False, allow_infinity=False)),
        y=draw(st.floats(min_value=-200.0, max_value=200.0, allow_nan=False, allow_infinity=False)),
    )


@composite
def _lines(draw: st.DrawFn) -> Line2D:
    return Line2D(start=draw(_points()), end=draw(_points()))


@composite
def _dart_geometries(draw: st.DrawFn) -> DartGeometry:
    return DartGeometry(
        apex=draw(_points()),
        angle=draw(st.floats(min_value=5.0, max_value=45.0, allow_nan=False, allow_infinity=False)),
        length=draw(st.floats(min_value=1.0, max_value=20.0, allow_nan=False, allow_infinity=False)),
    )


@composite
def _pattern_pieces(draw: st.DrawFn, piece_id: str = "front", label: str = "Front Bodice") -> PatternPiece:
    """Generate a valid PatternPiece with a closed outline."""
    # Generate 3-6 interior points, then close the polygon
    n_pts = draw(st.integers(min_value=3, max_value=6))
    pts = [draw(_points()) for _ in range(n_pts)]
    pts.append(pts[0])  # close the polygon
    return PatternPiece(
        piece_id=piece_id,
        label=label,
        outline=tuple(pts),
        seam_lines=(draw(_lines()),),
        darts=(draw(_dart_geometries()),),
        grain_line=draw(_lines()),
        notch_marks=(draw(_points()),),
        seam_allowance=draw(st.floats(min_value=0.5, max_value=3.0, allow_nan=False, allow_infinity=False)),
    )


@composite
def bodice_slopers(draw: st.DrawFn) -> BodiceSloper:
    """Generate valid BodiceSloper with proper geometry."""
    profile = draw(measurement_profiles())
    return BodiceSloper(
        sloper_id=draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))),
        profile=profile,
        front_bodice=draw(_pattern_pieces(piece_id="front", label="Front Bodice")),
        back_bodice=draw(_pattern_pieces(piece_id="back", label="Back Bodice")),
        bust_ease=draw(st.floats(min_value=0.5, max_value=10.0, allow_nan=False, allow_infinity=False)),
        waist_ease=draw(st.floats(min_value=0.5, max_value=10.0, allow_nan=False, allow_infinity=False)),
        metadata={"engine_version": "0.1.0"},
    )


@composite
def tension_maps(draw: st.DrawFn) -> TensionMap:
    """Generate valid TensionMaps with non-negative stresses."""
    n_vertices = draw(st.integers(min_value=10, max_value=200))
    stresses = np.array(
        [draw(st.floats(min_value=0.0, max_value=5000.0, allow_nan=False, allow_infinity=False))
         for _ in range(n_vertices)],
        dtype=np.float64,
    )
    n_collisions = draw(st.integers(min_value=0, max_value=min(5, n_vertices)))
    collision_indices = np.array(
        sorted(draw(st.sampled_from(range(n_vertices))) for _ in range(n_collisions)),
        dtype=np.int32,
    ) if n_collisions > 0 else np.array([], dtype=np.int32)
    return TensionMap(vertex_stresses=stresses, collision_vertices=collision_indices)


@composite
def fit_issues(draw: st.DrawFn) -> FitIssue:
    """Generate valid FitIssues."""
    region = draw(st.sampled_from(list(FitRegion)))
    issue_type = draw(st.sampled_from(list(FitIssueType)))
    threshold = draw(st.floats(min_value=100.0, max_value=2000.0, allow_nan=False, allow_infinity=False))
    violation = draw(st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    return FitIssue(
        region=region,
        issue_type=issue_type,
        measured_stress=threshold + violation,
        threshold=threshold,
        violation_magnitude=violation,
    )


@composite
def correction_strategies(draw: st.DrawFn) -> CorrectionStrategy:
    """Generate valid CorrectionStrategies."""
    return CorrectionStrategy(
        target_region=draw(st.sampled_from(list(FitRegion))),
        issue_type=draw(st.sampled_from(list(FitIssueType))),
        correction_type=draw(st.sampled_from(list(CorrectionType))),
        magnitude=draw(st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False)),
        dampening_factor=draw(st.floats(min_value=0.1, max_value=1.0, allow_nan=False, allow_infinity=False)),
    )


# ---------------------------------------------------------------------------
# Sample measurement profiles (fixtures)
# ---------------------------------------------------------------------------

SAMPLE_PROFILES = {
    "small": MeasurementProfile(chest=81.0, waist=63.5, hip=88.0, shoulder_width=37.0, torso_length=40.0),
    "medium": MeasurementProfile(chest=91.5, waist=73.5, hip=98.0, shoulder_width=40.0, torso_length=42.5),
    "large": MeasurementProfile(chest=102.0, waist=84.0, hip=109.0, shoulder_width=43.0, torso_length=44.0),
    "plus": MeasurementProfile(chest=117.0, waist=99.0, hip=122.0, shoulder_width=46.0, torso_length=45.5),
    "petite": MeasurementProfile(chest=83.0, waist=65.0, hip=90.0, shoulder_width=36.0, torso_length=37.5),
    "high_bust_ratio": MeasurementProfile(chest=107.0, waist=68.5, hip=97.0, shoulder_width=39.0, torso_length=43.0),
}


@pytest.fixture(params=SAMPLE_PROFILES.keys())
def sample_profile(request: pytest.FixtureRequest) -> MeasurementProfile:
    """Parametrized fixture yielding each sample MeasurementProfile."""
    return SAMPLE_PROFILES[request.param]
