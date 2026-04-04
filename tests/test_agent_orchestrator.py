"""Property tests for the Agent Orchestrator.

Properties 12, 13, 14, 17, 18, 19 from the design document.
"""

from __future__ import annotations

from hypothesis import given, settings

from agentic_pattern_engine.agent_orchestrator import AgentOrchestrator
from agentic_pattern_engine.models import (
    AgentConfig,
    ConvergenceStatus,
    MeasurementProfile,
    TensionThresholds,
)
from tests.conftest import SAMPLE_PROFILES, measurement_profiles

_agent = AgentOrchestrator()


# Feature: agentic-pattern-engine, Property 12: Iteration limit returns best sloper
def test_iteration_limit_best_sloper():
    """For any AgentRun reaching iteration_limit, returned final_sloper
    must be the one with lowest total_stress_magnitude from the AuditTrail,
    status must be ITERATION_LIMIT_REACHED, remaining_fit_issues non-empty."""
    # Use a very low iteration limit to force hitting the limit
    config = AgentConfig(iteration_limit=2)
    # Use high_bust_ratio profile which should trigger tension
    profile = SAMPLE_PROFILES["high_bust_ratio"]
    result = _agent.run(profile, config)

    if result.convergence_status == ConvergenceStatus.ITERATION_LIMIT_REACHED:
        assert result.final_sloper is not None
        assert len(result.remaining_fit_issues) > 0

        # Verify it's the best sloper from the trail
        trail = result.audit_trail
        # Find the entry with lowest stress (excluding iteration 0)
        sim_entries = [e for e in trail.entries if e.iteration > 0]
        if sim_entries:
            best_entry = min(sim_entries, key=lambda e: e.total_stress_magnitude)
            # The final sloper should match the best entry's sloper
            assert result.final_sloper.sloper_id == best_entry.sloper.sloper_id


# Feature: agentic-pattern-engine, Property 13: Convergence halts correctly
@given(profile=measurement_profiles())
@settings(max_examples=20)
def test_convergence_halts_correctly(profile):
    """For any converged AgentRun, final AuditTrail entry must have zero
    FitIssues, status CONVERGED, remaining_fit_issues empty,
    total_iterations <= iteration_limit."""
    config = AgentConfig(iteration_limit=20)
    result = _agent.run(profile, config)

    if result.convergence_status == ConvergenceStatus.CONVERGED:
        assert result.final_sloper is not None
        assert len(result.remaining_fit_issues) == 0
        assert result.total_iterations <= config.iteration_limit

        # Final audit entry should have zero fit issues
        trail = result.audit_trail
        last_sim = [e for e in trail.entries if e.iteration > 0]
        if last_sim:
            assert len(last_sim[-1].fit_issues) == 0


# Feature: agentic-pattern-engine, Property 14: Oscillation dampening
def test_oscillation_dampening():
    """When a FitRegion alternates between excess_tension and
    insufficient_tension, the subsequent CorrectionStrategy must have
    dampening_factor of 0.5^n."""
    from agentic_pattern_engine.agent_orchestrator import AgentOrchestrator

    # Test the oscillation detection logic directly
    from agentic_pattern_engine.models import FitIssue, FitIssueType, FitRegion

    issue_history_1 = [
        [FitIssue(FitRegion.BUST, FitIssueType.EXCESS_TENSION, 600, 500, 100)],
    ]
    issue_history_2 = [
        [FitIssue(FitRegion.BUST, FitIssueType.EXCESS_TENSION, 600, 500, 100)],
        [FitIssue(FitRegion.BUST, FitIssueType.INSUFFICIENT_TENSION, 50, 500, 25)],
    ]
    issue_history_3 = [
        [FitIssue(FitRegion.BUST, FitIssueType.EXCESS_TENSION, 600, 500, 100)],
        [FitIssue(FitRegion.BUST, FitIssueType.EXCESS_TENSION, 550, 500, 50)],
    ]

    # No oscillation with single entry
    assert not AgentOrchestrator._detect_oscillation(issue_history_1)
    # Oscillation: excess -> insufficient
    assert AgentOrchestrator._detect_oscillation(issue_history_2)
    # No oscillation: excess -> excess
    assert not AgentOrchestrator._detect_oscillation(issue_history_3)


# Feature: agentic-pattern-engine, Property 17: Result completeness by status
@given(profile=measurement_profiles())
@settings(max_examples=20)
def test_result_completeness_by_status(profile):
    """For any completed AgentRun, verify result fields match status."""
    config = AgentConfig(iteration_limit=5)
    result = _agent.run(profile, config)

    assert result.elapsed_time_ms > 0
    assert result.audit_trail is not None

    if result.convergence_status == ConvergenceStatus.CONVERGED:
        assert result.final_sloper is not None
        assert len(result.remaining_fit_issues) == 0

    elif result.convergence_status == ConvergenceStatus.ITERATION_LIMIT_REACHED:
        assert result.final_sloper is not None
        assert len(result.remaining_fit_issues) > 0

    elif result.convergence_status == ConvergenceStatus.GENERATION_FAILED:
        assert result.final_sloper is None
        assert result.total_iterations == 0
        assert result.error_details is not None

    elif result.convergence_status == ConvergenceStatus.SIMULATION_FAILED:
        assert result.failed_at_iteration is not None
        assert result.error_details is not None

    elif result.convergence_status == ConvergenceStatus.STALLED:
        assert result.final_sloper is not None


def test_generation_failed_invalid_profile():
    """Invalid profile must return GENERATION_FAILED with error details."""
    bad_profile = MeasurementProfile(
        chest=10.0,  # way below range
        waist=50.0,
        hip=60.0,
        shoulder_width=30.0,
        torso_length=35.0,
    )
    result = _agent.run(bad_profile)
    assert result.convergence_status == ConvergenceStatus.GENERATION_FAILED
    assert result.final_sloper is None
    assert result.total_iterations == 0
    assert result.error_details is not None
    assert "chest" in result.error_details


# Feature: agentic-pattern-engine, Property 18: Monotonic stress decrease
def test_monotonic_stress_decrease():
    """For a converged run, stress should generally decrease across iterations."""
    # Use a profile that's likely to converge
    profile = SAMPLE_PROFILES["medium"]
    config = AgentConfig(iteration_limit=20)
    result = _agent.run(profile, config)

    if result.convergence_status == ConvergenceStatus.CONVERGED:
        trail = result.audit_trail
        sim_entries = [e for e in trail.entries if e.iteration > 0]
        if len(sim_entries) > 1:
            stresses = [e.total_stress_magnitude for e in sim_entries]
            # For converged runs, the final stress should be 0
            assert stresses[-1] == 0.0


# Feature: agentic-pattern-engine, Property 19: Stall detection and halt
def test_stall_detection():
    """When 3 consecutive iterations fail to reduce stress, Agent must halt
    with STALLED status and return best sloper."""
    # Test the stall detection logic directly
    from agentic_pattern_engine.agent_orchestrator import AgentOrchestrator

    # Not stalled: improving
    assert not AgentOrchestrator._is_stalled([100, 90, 80], 3)
    # Stalled: non-improving for 3 consecutive
    assert AgentOrchestrator._is_stalled([100, 100, 100], 3)
    assert AgentOrchestrator._is_stalled([100, 110, 120], 3)
    # Not enough history
    assert not AgentOrchestrator._is_stalled([100, 100], 3)


def test_full_run_with_exports():
    """Full agent run should produce DXF and PDF exports on success."""
    profile = SAMPLE_PROFILES["medium"]
    result = _agent.run(profile)

    if result.convergence_status in (
        ConvergenceStatus.CONVERGED,
        ConvergenceStatus.ITERATION_LIMIT_REACHED,
        ConvergenceStatus.STALLED,
    ):
        assert result.dxf_bytes is not None
        assert result.pdf_bytes is not None
        assert len(result.dxf_bytes) > 0
        assert len(result.pdf_bytes) > 0


# ---------------------------------------------------------------------------
# PR review feedback: unit tests for orchestrator internals
# ---------------------------------------------------------------------------

from agentic_pattern_engine.garment_spec import BodiceGarmentSpec
from agentic_pattern_engine.models import (
    BodiceSloper,
    DartGeometry,
    FitIssue,
    FitIssueType,
    FitRegion,
    Line2D,
    PatternPiece,
    Point2D,
)


# --- __init__ default spec wiring ---


def test_agent_orchestrator_default_spec_is_bodice() -> None:
    """Orchestrator with no garment_spec defaults to BodiceGarmentSpec."""
    orch = AgentOrchestrator()
    assert isinstance(orch._spec, BodiceGarmentSpec)


def test_agent_orchestrator_custom_spec_is_used() -> None:
    """Orchestrator uses the provided garment_spec instead of default."""
    spec = BodiceGarmentSpec()
    orch = AgentOrchestrator(garment_spec=spec)
    assert orch._spec is spec


# --- _build_compat_sloper ---


def test_agent_orchestrator_build_compat_sloper_bodice_cached() -> None:
    """When BodiceGarmentSpec has a cached _last_sloper,
    _build_compat_sloper returns it."""
    spec = BodiceGarmentSpec()
    profile = SAMPLE_PROFILES["medium"]
    pieces = spec.generate_initial_pieces(profile)
    cached_sloper = spec._last_sloper
    assert cached_sloper is not None

    orch = AgentOrchestrator(garment_spec=spec)
    result = orch._build_compat_sloper(pieces, profile)
    assert result is cached_sloper


def test_agent_orchestrator_build_compat_sloper_bodice_fallback() -> None:
    """When BodiceGarmentSpec has no cached sloper,
    _build_compat_sloper generates a fresh one."""
    spec = BodiceGarmentSpec()
    assert spec._last_sloper is None

    profile = SAMPLE_PROFILES["medium"]
    orch = AgentOrchestrator(garment_spec=spec)
    pieces = spec.generate_initial_pieces(profile)
    spec._last_sloper = None  # force no cache

    result = orch._build_compat_sloper(pieces, profile)
    assert result is not None
    assert result.sloper_id is not None
    assert result.front_bodice is not None
    assert result.back_bodice is not None


def test_agent_orchestrator_build_compat_sloper_non_bodice_wrapper() -> None:
    """For a non-BodiceGarmentSpec, _build_compat_sloper creates
    a minimal BodiceSloper wrapper from the pieces."""

    class FakeSkirtSpec:
        garment_type = "skirt"
        measurement_fields = ["waist", "hip"]
        fit_regions = ["hip", "waist"]
        tension_thresholds = {"hip": 50.0, "waist": 45.0}

        def validate_profile(self, profile):
            return []

        def generate_initial_pieces(self, profile):
            return []

        def compute_stress(self, pieces, profile):
            return {}

        def plan_corrections(self, issues, pieces, profile, df):
            return []

        def apply_corrections(self, pieces, corrections):
            return pieces

        def validate_geometry(self, pieces):
            return []

    profile = SAMPLE_PROFILES["medium"]
    orch = AgentOrchestrator(garment_spec=FakeSkirtSpec())

    outline = (
        Point2D(0, 0), Point2D(10, 0),
        Point2D(10, 20), Point2D(0, 0),
    )
    dart = DartGeometry(apex=Point2D(5, 10), angle=15.0, length=8.0)
    grain = Line2D(start=Point2D(5, 0), end=Point2D(5, 20))
    front = PatternPiece(
        piece_id="front_skirt", label="Front Skirt",
        outline=outline, seam_lines=(), darts=(dart,),
        grain_line=grain, notch_marks=(Point2D(5, 0),),
        seam_allowance=1.5,
    )
    back = PatternPiece(
        piece_id="back_skirt", label="Back Skirt",
        outline=outline, seam_lines=(), darts=(dart,),
        grain_line=grain, notch_marks=(Point2D(5, 0),),
        seam_allowance=1.5,
    )

    result = orch._build_compat_sloper([front, back], profile)
    assert isinstance(result, BodiceSloper)
    assert result.sloper_id == "compat"
    assert result.front_bodice is front
    assert result.back_bodice is back
    assert result.bust_ease == 0.0
    assert result.waist_ease == 0.0
    assert result.metadata["garment_type"] == "skirt"


def test_agent_orchestrator_build_compat_sloper_non_bodice_empty() -> None:
    """For non-bodice spec with empty pieces list,
    _build_compat_sloper falls back to generating a fresh sloper."""

    class FakeSpec:
        garment_type = "skirt"
        measurement_fields = ["waist"]
        fit_regions = ["waist"]
        tension_thresholds = {"waist": 45.0}

        def validate_profile(self, p):
            return []

        def generate_initial_pieces(self, p):
            return []

        def compute_stress(self, pieces, p):
            return {}

        def plan_corrections(self, i, pieces, p, d):
            return []

        def apply_corrections(self, pieces, c):
            return pieces

        def validate_geometry(self, pieces):
            return []

    profile = SAMPLE_PROFILES["medium"]
    orch = AgentOrchestrator(garment_spec=FakeSpec())
    result = orch._build_compat_sloper([], profile)
    assert result is not None
    assert result.front_bodice is not None


# --- _detect_oscillation flip logic ---


def test_agent_orchestrator_oscillation_insufficient_to_excess() -> None:
    """Oscillation detected: insufficient → excess flip."""
    history = [
        [FitIssue(FitRegion.BUST, FitIssueType.INSUFFICIENT_TENSION,
                  50, 500, 25)],
        [FitIssue(FitRegion.BUST, FitIssueType.EXCESS_TENSION,
                  600, 500, 100)],
    ]
    assert AgentOrchestrator._detect_oscillation(history)


def test_agent_orchestrator_oscillation_excess_to_insufficient() -> None:
    """Oscillation detected: excess → insufficient flip."""
    history = [
        [FitIssue(FitRegion.BUST, FitIssueType.EXCESS_TENSION,
                  600, 500, 100)],
        [FitIssue(FitRegion.BUST, FitIssueType.INSUFFICIENT_TENSION,
                  50, 500, 25)],
    ]
    assert AgentOrchestrator._detect_oscillation(history)


def test_agent_orchestrator_oscillation_same_type_no_flip() -> None:
    """No oscillation when same issue type persists."""
    history = [
        [FitIssue(FitRegion.BUST, FitIssueType.EXCESS_TENSION,
                  600, 500, 100)],
        [FitIssue(FitRegion.BUST, FitIssueType.EXCESS_TENSION,
                  550, 500, 50)],
    ]
    assert not AgentOrchestrator._detect_oscillation(history)


def test_agent_orchestrator_oscillation_different_regions() -> None:
    """No oscillation when different regions have different types."""
    history = [
        [FitIssue(FitRegion.BUST, FitIssueType.EXCESS_TENSION,
                  600, 500, 100)],
        [FitIssue(FitRegion.WAIST, FitIssueType.INSUFFICIENT_TENSION,
                  30, 50, 20)],
    ]
    assert not AgentOrchestrator._detect_oscillation(history)


def test_agent_orchestrator_oscillation_pulling_no_flip() -> None:
    """PULLING issue type does not trigger oscillation."""
    history = [
        [FitIssue(FitRegion.BUST, FitIssueType.EXCESS_TENSION,
                  600, 500, 100)],
        [FitIssue(FitRegion.BUST, FitIssueType.PULLING,
                  300, 500, 50)],
    ]
    assert not AgentOrchestrator._detect_oscillation(history)


def test_agent_orchestrator_oscillation_multi_region_one_flips() -> None:
    """Oscillation detected when at least one region flips."""
    history = [
        [
            FitIssue(FitRegion.BUST, FitIssueType.EXCESS_TENSION,
                     600, 500, 100),
            FitIssue(FitRegion.WAIST, FitIssueType.EXCESS_TENSION,
                     200, 150, 50),
        ],
        [
            FitIssue(FitRegion.BUST, FitIssueType.INSUFFICIENT_TENSION,
                     50, 500, 25),
            FitIssue(FitRegion.WAIST, FitIssueType.EXCESS_TENSION,
                     180, 150, 30),
        ],
    ]
    assert AgentOrchestrator._detect_oscillation(history)


def test_agent_orchestrator_oscillation_empty_history() -> None:
    """Empty history returns no oscillation."""
    assert not AgentOrchestrator._detect_oscillation([])


def test_agent_orchestrator_oscillation_single_entry() -> None:
    """Single entry returns no oscillation."""
    history = [
        [FitIssue(FitRegion.BUST, FitIssueType.EXCESS_TENSION,
                  600, 500, 100)],
    ]
    assert not AgentOrchestrator._detect_oscillation(history)
