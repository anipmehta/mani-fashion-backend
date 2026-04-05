"""Tests for GarmentSpec protocol and BodiceGarmentSpec implementation."""

from __future__ import annotations

import json
import math

import pytest

from agentic_pattern_engine.agent_orchestrator import AgentOrchestrator
from agentic_pattern_engine.garment_spec import (
    BodiceGarmentSpec,
    GarmentSpec,
)
from agentic_pattern_engine.models import (
    AgentConfig,
    ConvergenceStatus,
    FitIssue,
    FitIssueType,
    FitRegion,
    MeasurementProfile,
)
from tests.conftest import SAMPLE_PROFILES


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_garment_spec_bodice_is_runtime_checkable() -> None:
    """BodiceGarmentSpec satisfies the GarmentSpec protocol."""
    spec = BodiceGarmentSpec()
    assert isinstance(spec, GarmentSpec)


def test_garment_spec_bodice_garment_type() -> None:
    spec = BodiceGarmentSpec()
    assert spec.garment_type == BodiceGarmentSpec.GARMENT_TYPE


def test_garment_spec_bodice_measurement_fields() -> None:
    spec = BodiceGarmentSpec()
    fields = spec.measurement_fields
    assert isinstance(fields, list)
    assert len(fields) > 0
    for f in BodiceGarmentSpec.MEASUREMENT_FIELDS:
        assert f in fields


def test_garment_spec_bodice_fit_regions_nonempty() -> None:
    spec = BodiceGarmentSpec()
    regions = spec.fit_regions
    assert isinstance(regions, list)
    assert len(regions) > 0
    for r in BodiceGarmentSpec.FIT_REGIONS:
        assert r in regions


def test_garment_spec_bodice_tension_thresholds_positive() -> None:
    spec = BodiceGarmentSpec()
    thresholds = spec.tension_thresholds
    assert isinstance(thresholds, dict)
    for region in spec.fit_regions:
        assert region in thresholds
        assert thresholds[region] > 0


# ---------------------------------------------------------------------------
# validate_profile
# ---------------------------------------------------------------------------


def test_garment_spec_bodice_validate_valid_profile() -> None:
    spec = BodiceGarmentSpec()
    profile = SAMPLE_PROFILES["medium"]
    errors = spec.validate_profile(profile)
    assert errors == []


def test_garment_spec_bodice_validate_invalid_profile() -> None:
    spec = BodiceGarmentSpec()
    bad = MeasurementProfile(
        chest=10.0, waist=73.5, hip=98.0,
        shoulder_width=40.0, torso_length=42.5,
    )
    errors = spec.validate_profile(bad)
    assert len(errors) > 0
    assert any("chest" in e for e in errors)


# ---------------------------------------------------------------------------
# generate_initial_pieces
# ---------------------------------------------------------------------------


def test_garment_spec_bodice_generates_two_pieces() -> None:
    spec = BodiceGarmentSpec()
    profile = SAMPLE_PROFILES["medium"]
    pieces = spec.generate_initial_pieces(profile)
    assert len(pieces) == 2
    assert pieces[0].piece_id == "front_bodice"
    assert pieces[1].piece_id == "back_bodice"


def test_garment_spec_bodice_pieces_have_closed_outlines() -> None:
    spec = BodiceGarmentSpec()
    profile = SAMPLE_PROFILES["medium"]
    pieces = spec.generate_initial_pieces(profile)
    for piece in pieces:
        assert piece.outline[0] == piece.outline[-1]


# ---------------------------------------------------------------------------
# compute_stress
# ---------------------------------------------------------------------------


def test_garment_spec_bodice_compute_stress_returns_all_regions() -> None:
    spec = BodiceGarmentSpec()
    profile = SAMPLE_PROFILES["medium"]
    pieces = spec.generate_initial_pieces(profile)
    stresses = spec.compute_stress(pieces, profile)
    assert isinstance(stresses, dict)
    for region in spec.fit_regions:
        assert region in stresses
        assert isinstance(stresses[region], float)


def test_garment_spec_bodice_stress_nonnegative() -> None:
    spec = BodiceGarmentSpec()
    profile = SAMPLE_PROFILES["medium"]
    pieces = spec.generate_initial_pieces(profile)
    stresses = spec.compute_stress(pieces, profile)
    for region, val in stresses.items():
        assert val >= 0.0, f"{region} stress is negative: {val}"


# ---------------------------------------------------------------------------
# plan_corrections + apply_corrections
# ---------------------------------------------------------------------------


def test_garment_spec_bodice_plan_corrections_for_excess() -> None:
    spec = BodiceGarmentSpec()
    profile = SAMPLE_PROFILES["medium"]
    pieces = spec.generate_initial_pieces(profile)
    issues = [
        FitIssue(
            region=FitRegion.BUST,
            issue_type=FitIssueType.EXCESS_TENSION,
            measured_stress=100.0,
            threshold=60.0,
            violation_magnitude=40.0,
        ),
    ]
    corrections = spec.plan_corrections(
        issues, pieces, profile, 1.0,
    )
    assert len(corrections) > 0


def test_garment_spec_bodice_apply_corrections_returns_two_pieces() -> None:
    spec = BodiceGarmentSpec()
    profile = SAMPLE_PROFILES["medium"]
    pieces = spec.generate_initial_pieces(profile)
    issues = [
        FitIssue(
            region=FitRegion.BUST,
            issue_type=FitIssueType.EXCESS_TENSION,
            measured_stress=100.0,
            threshold=60.0,
            violation_magnitude=40.0,
        ),
    ]
    corrections = spec.plan_corrections(
        issues, pieces, profile, 1.0,
    )
    updated = spec.apply_corrections(pieces, corrections)
    assert len(updated) == 2
    assert updated[0].piece_id == "front_bodice"


# ---------------------------------------------------------------------------
# validate_geometry
# ---------------------------------------------------------------------------


def test_garment_spec_bodice_validate_geometry_valid() -> None:
    spec = BodiceGarmentSpec()
    profile = SAMPLE_PROFILES["medium"]
    pieces = spec.generate_initial_pieces(profile)
    errors = spec.validate_geometry(pieces)
    assert errors == []


# ---------------------------------------------------------------------------
# Orchestrator with explicit BodiceGarmentSpec matches default
# ---------------------------------------------------------------------------


def test_garment_spec_orchestrator_with_explicit_spec_matches() -> None:
    """Running orchestrator with explicit BodiceGarmentSpec should
    produce identical convergence_status and total_iterations as
    the default (no spec) orchestrator."""
    profile = SAMPLE_PROFILES["medium"]
    cfg = AgentConfig(iteration_limit=10)

    # Default orchestrator (backward compat)
    orch_default = AgentOrchestrator()
    result_default = orch_default.run(profile, cfg)

    # Explicit BodiceGarmentSpec
    spec = BodiceGarmentSpec()
    orch_spec = AgentOrchestrator(garment_spec=spec)
    result_spec = orch_spec.run(profile, cfg)

    assert result_default.convergence_status == result_spec.convergence_status
    assert result_default.total_iterations == result_spec.total_iterations
    assert result_spec.garment_type == BodiceGarmentSpec.GARMENT_TYPE
    assert result_spec.final_pieces is not None
    assert len(result_spec.final_pieces) == 2


def test_garment_spec_orchestrator_result_has_garment_fields() -> None:
    """AgentRunResult should have final_pieces and garment_type."""
    profile = SAMPLE_PROFILES["small"]
    cfg = AgentConfig(iteration_limit=5)
    orch = AgentOrchestrator()
    result = orch.run(profile, cfg)
    assert result.garment_type == BodiceGarmentSpec.GARMENT_TYPE
    assert result.final_pieces is not None


@pytest.mark.parametrize("profile_name", list(SAMPLE_PROFILES.keys()))
def test_garment_spec_orchestrator_regression_all_profiles(
    profile_name: str,
) -> None:
    """Explicit BodiceGarmentSpec produces same convergence as default
    for all sample profiles."""
    profile = SAMPLE_PROFILES[profile_name]
    cfg = AgentConfig(iteration_limit=10)

    result_default = AgentOrchestrator().run(profile, cfg)
    result_spec = AgentOrchestrator(
        garment_spec=BodiceGarmentSpec(),
    ).run(profile, cfg)

    assert result_default.convergence_status == result_spec.convergence_status
    assert result_default.total_iterations == result_spec.total_iterations

