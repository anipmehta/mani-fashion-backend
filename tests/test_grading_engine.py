"""Tests for GradingEngine — delta computation, scaling, and self-correction."""

from __future__ import annotations

import pytest

from agentic_pattern_engine.agent_orchestrator import AgentOrchestrator
from agentic_pattern_engine.grading_engine import (
    LARGE_DELTA_THRESHOLD,
    GradingEngine,
)
from agentic_pattern_engine.models import (
    DartGeometry,
    Line2D,
    MeasurementProfile,
    PatternPiece,
    Point2D,
    SkirtMeasurementProfile,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SOURCE_BODICE = MeasurementProfile(
    chest=91.5, waist=73.5, hip=98.0,
    shoulder_width=40.0, torso_length=42.5,
)

_TARGET_BODICE = MeasurementProfile(
    chest=102.0, waist=84.0, hip=109.0,
    shoulder_width=43.0, torso_length=44.0,
)

_LARGE_TARGET_BODICE = MeasurementProfile(
    chest=117.0, waist=99.0, hip=122.0,
    shoulder_width=46.0, torso_length=45.5,
)


def _make_piece(
    piece_id: str = "front",
    label: str = "Front Bodice",
) -> PatternPiece:
    """Create a simple test pattern piece."""
    return PatternPiece(
        piece_id=piece_id,
        label=label,
        outline=(
            Point2D(0, 0), Point2D(20, 0),
            Point2D(20, 30), Point2D(0, 30), Point2D(0, 0),
        ),
        seam_lines=(
            Line2D(Point2D(0, 0), Point2D(20, 0)),
            Line2D(Point2D(20, 0), Point2D(20, 30)),
        ),
        darts=(
            DartGeometry(apex=Point2D(10, 0), angle=12.0, length=8.0),
        ),
        grain_line=Line2D(Point2D(10, 2), Point2D(10, 28)),
        notch_marks=(Point2D(5, 0), Point2D(15, 15)),
        seam_allowance=1.5,
    )


# ---------------------------------------------------------------------------
# Delta computation tests
# ---------------------------------------------------------------------------


def test_grading_engine_delta_computation_bodice():
    """Deltas should be target - source for each bodice field."""
    engine = GradingEngine()
    deltas = engine._compute_deltas(
        _SOURCE_BODICE, _TARGET_BODICE, "bodice",
    )

    assert abs(deltas["chest"] - 10.5) < 0.01
    assert abs(deltas["waist"] - 10.5) < 0.01
    assert abs(deltas["hip"] - 11.0) < 0.01
    assert abs(deltas["shoulder_width"] - 3.0) < 0.01
    assert abs(deltas["torso_length"] - 1.5) < 0.01


def test_grading_engine_delta_computation_skirt():
    """Deltas should use skirt fields for skirt garment type."""
    source = SkirtMeasurementProfile(
        waist=73.5, hip=98.0, hip_depth=20.0, desired_length=70.0,
    )
    target = SkirtMeasurementProfile(
        waist=84.0, hip=109.0, hip_depth=22.0, desired_length=75.0,
    )
    engine = GradingEngine()
    deltas = engine._compute_deltas(source, target, "skirt")

    assert abs(deltas["waist"] - 10.5) < 0.01
    assert abs(deltas["hip"] - 11.0) < 0.01
    assert abs(deltas["hip_depth"] - 2.0) < 0.01
    assert abs(deltas["desired_length"] - 5.0) < 0.01
    # Should NOT have bodice-only fields
    assert "chest" not in deltas
    assert "shoulder_width" not in deltas


# ---------------------------------------------------------------------------
# Proportional scaling tests
# ---------------------------------------------------------------------------


def test_grading_engine_scaling_preserves_dart_count():
    """Scaling should preserve the number of darts."""
    engine = GradingEngine()
    pieces = [_make_piece(), _make_piece("back", "Back Bodice")]

    result = engine.grade(
        pieces, _SOURCE_BODICE, _TARGET_BODICE, "bodice",
    )

    for orig, graded in zip(pieces, result.graded_pieces):
        assert len(graded.darts) == len(orig.darts)


def test_grading_engine_scaling_preserves_seam_allowance():
    """Seam allowance should NOT be scaled."""
    engine = GradingEngine()
    pieces = [_make_piece()]

    result = engine.grade(
        pieces, _SOURCE_BODICE, _TARGET_BODICE, "bodice",
    )

    for orig, graded in zip(pieces, result.graded_pieces):
        assert graded.seam_allowance == orig.seam_allowance


def test_grading_engine_scaling_increases_outline():
    """Grading up should increase outline dimensions."""
    engine = GradingEngine()
    pieces = [_make_piece()]

    result = engine.grade(
        pieces, _SOURCE_BODICE, _TARGET_BODICE, "bodice",
    )

    orig_max_x = max(p.x for p in pieces[0].outline)
    graded_max_x = max(p.x for p in result.graded_pieces[0].outline)
    assert graded_max_x > orig_max_x


def test_grading_engine_scaling_preserves_dart_angle():
    """Dart angles should be preserved during scaling."""
    engine = GradingEngine()
    pieces = [_make_piece()]

    result = engine.grade(
        pieces, _SOURCE_BODICE, _TARGET_BODICE, "bodice",
    )

    for orig, graded in zip(pieces, result.graded_pieces):
        for od, gd in zip(orig.darts, graded.darts):
            assert abs(od.angle - gd.angle) < 0.001


# ---------------------------------------------------------------------------
# Large delta warning tests
# ---------------------------------------------------------------------------


def test_grading_engine_large_delta_produces_warning():
    """Delta > 15 cm should produce a warning."""
    engine = GradingEngine()
    pieces = [_make_piece()]

    result = engine.grade(
        pieces, _SOURCE_BODICE, _LARGE_TARGET_BODICE, "bodice",
    )

    # chest delta = 117 - 91.5 = 25.5 > 15
    assert len(result.warnings) > 0
    assert any("Large grade jump" in w for w in result.warnings)


def test_grading_engine_small_delta_no_warning():
    """Delta < 15 cm should not produce a warning."""
    small_target = MeasurementProfile(
        chest=95.0, waist=77.0, hip=102.0,
        shoulder_width=41.0, torso_length=43.0,
    )
    engine = GradingEngine()
    pieces = [_make_piece()]

    result = engine.grade(
        pieces, _SOURCE_BODICE, small_target, "bodice",
    )

    assert not any("Large grade jump" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Self-correction integration tests
# ---------------------------------------------------------------------------


def test_grading_engine_with_orchestrator_runs_self_correction():
    """Grading with orchestrator should run self-correction."""
    orchestrator = AgentOrchestrator()
    engine = GradingEngine(orchestrator=orchestrator)
    pieces = [_make_piece(), _make_piece("back", "Back Bodice")]

    result = engine.grade(
        pieces, _SOURCE_BODICE, _TARGET_BODICE, "bodice",
    )

    assert result.run_result is not None
    assert result.run_result.convergence_status is not None


def test_grading_engine_without_orchestrator_no_run_result():
    """Grading without orchestrator should return None run_result."""
    engine = GradingEngine()
    pieces = [_make_piece()]

    result = engine.grade(
        pieces, _SOURCE_BODICE, _TARGET_BODICE, "bodice",
    )

    assert result.run_result is None
    assert len(result.graded_pieces) == 1


def test_grading_engine_deltas_stored_in_result():
    """Deltas should be stored in the GradingResult."""
    engine = GradingEngine()
    pieces = [_make_piece()]

    result = engine.grade(
        pieces, _SOURCE_BODICE, _TARGET_BODICE, "bodice",
    )

    assert "chest" in result.deltas
    assert "waist" in result.deltas
    assert abs(result.deltas["chest"] - 10.5) < 0.01


def test_grading_engine_original_pieces_preserved():
    """Original pieces should be stored unchanged in result."""
    engine = GradingEngine()
    pieces = [_make_piece()]

    result = engine.grade(
        pieces, _SOURCE_BODICE, _TARGET_BODICE, "bodice",
    )

    assert result.original_pieces == pieces
