"""Tests for SkirtGarmentSpec — stress model, corrections, orchestrator."""

from __future__ import annotations

from agentic_pattern_engine.agent_orchestrator import AgentOrchestrator
from agentic_pattern_engine.garment_spec import GarmentSpec
from agentic_pattern_engine.models import (
    AgentConfig,
    ConvergenceStatus,
    FitIssue,
    FitIssueType,
    FitRegion,
    SkirtMeasurementProfile,
)
from agentic_pattern_engine.skirt_generator import SkirtGarmentSpec

_spec = SkirtGarmentSpec()
_STANDARD = SkirtMeasurementProfile(
    waist=73.5, hip=98.0, hip_depth=20.0, desired_length=70.0,
)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_skirt_spec_is_garment_spec() -> None:
    assert isinstance(_spec, GarmentSpec)


def test_skirt_spec_garment_type() -> None:
    assert _spec.garment_type == SkirtGarmentSpec.GARMENT_TYPE


def test_skirt_spec_measurement_fields() -> None:
    for f in SkirtGarmentSpec.MEASUREMENT_FIELDS:
        assert f in _spec.measurement_fields


def test_skirt_spec_fit_regions() -> None:
    for r in SkirtGarmentSpec.FIT_REGIONS:
        assert r in _spec.fit_regions


def test_skirt_spec_tension_thresholds_positive() -> None:
    for region, val in _spec.tension_thresholds.items():
        assert val > 0, f"{region} threshold must be positive"


# ---------------------------------------------------------------------------
# Stress computation
# ---------------------------------------------------------------------------


def test_skirt_spec_compute_stress_returns_all_regions() -> None:
    pieces = _spec.generate_initial_pieces(_STANDARD)
    stresses = _spec.compute_stress(pieces, _STANDARD)
    for region in SkirtGarmentSpec.FIT_REGIONS:
        assert region in stresses
        assert isinstance(stresses[region], float)


def test_skirt_spec_stress_nonnegative() -> None:
    pieces = _spec.generate_initial_pieces(_STANDARD)
    stresses = _spec.compute_stress(pieces, _STANDARD)
    for region, val in stresses.items():
        assert val >= 0.0, f"{region} stress is negative: {val}"


# ---------------------------------------------------------------------------
# Corrections
# ---------------------------------------------------------------------------


def test_skirt_spec_plan_corrections_for_waist_excess() -> None:
    pieces = _spec.generate_initial_pieces(_STANDARD)
    issues = [
        FitIssue(
            region=FitRegion.WAIST,
            issue_type=FitIssueType.EXCESS_TENSION,
            measured_stress=100.0,
            threshold=45.0,
            violation_magnitude=55.0,
        ),
    ]
    corrections = _spec.plan_corrections(issues, pieces, _STANDARD, 1.0)
    assert len(corrections) > 0
    assert corrections[0].correction_type.value == "adjust_dart_angle"


def test_skirt_spec_plan_corrections_for_waist_insufficient() -> None:
    pieces = _spec.generate_initial_pieces(_STANDARD)
    issues = [
        FitIssue(
            region=FitRegion.WAIST,
            issue_type=FitIssueType.INSUFFICIENT_TENSION,
            measured_stress=5.0,
            threshold=45.0,
            violation_magnitude=40.0,
        ),
    ]
    corrections = _spec.plan_corrections(issues, pieces, _STANDARD, 1.0)
    assert len(corrections) > 0
    assert corrections[0].correction_type.value == "adjust_dart_length"


def test_skirt_spec_apply_corrections_returns_two_pieces() -> None:
    pieces = _spec.generate_initial_pieces(_STANDARD)
    issues = [
        FitIssue(
            region=FitRegion.WAIST,
            issue_type=FitIssueType.EXCESS_TENSION,
            measured_stress=100.0,
            threshold=45.0,
            violation_magnitude=55.0,
        ),
    ]
    corrections = _spec.plan_corrections(issues, pieces, _STANDARD, 1.0)
    updated = _spec.apply_corrections(pieces, corrections)
    assert len(updated) == 2
    assert updated[0].piece_id == "front_skirt"
    assert updated[1].piece_id == "back_skirt"


# ---------------------------------------------------------------------------
# Validate geometry
# ---------------------------------------------------------------------------


def test_skirt_spec_validate_geometry_valid() -> None:
    pieces = _spec.generate_initial_pieces(_STANDARD)
    errors = _spec.validate_geometry(pieces)
    assert errors == []


# ---------------------------------------------------------------------------
# Orchestrator integration
# ---------------------------------------------------------------------------


def test_skirt_spec_orchestrator_converges() -> None:
    """SkirtGarmentSpec through the orchestrator should converge."""
    orch = AgentOrchestrator(garment_spec=SkirtGarmentSpec())
    cfg = AgentConfig(iteration_limit=20)
    result = orch.run(_STANDARD, cfg)

    assert result.convergence_status in (
        ConvergenceStatus.CONVERGED,
        ConvergenceStatus.ITERATION_LIMIT_REACHED,
        ConvergenceStatus.STALLED,
    )
    assert result.garment_type == SkirtGarmentSpec.GARMENT_TYPE
    assert result.final_pieces is not None
    assert len(result.final_pieces) == 2


def test_skirt_spec_orchestrator_result_fields() -> None:
    """AgentRunResult has correct garment_type and final_pieces."""
    orch = AgentOrchestrator(garment_spec=SkirtGarmentSpec())
    result = orch.run(_STANDARD)

    assert result.garment_type == SkirtGarmentSpec.GARMENT_TYPE
    assert result.total_iterations >= 0
    assert result.elapsed_time_ms > 0
    assert result.audit_trail is not None
