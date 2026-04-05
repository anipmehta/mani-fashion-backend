"""Tests for SkirtGenerator and SkirtMeasurementProfile.

Covers tasks 4.2 (model validation) and 4.5 (generator unit tests).
"""

from __future__ import annotations

import pytest

from agentic_pattern_engine.models import SkirtMeasurementProfile
from agentic_pattern_engine.skirt_generator import SkirtGenerator

_generator = SkirtGenerator()

# Standard test profile
_STANDARD = SkirtMeasurementProfile(
    waist=73.5, hip=98.0, hip_depth=20.0, desired_length=70.0,
)
_PETITE = SkirtMeasurementProfile(
    waist=63.0, hip=88.0, hip_depth=18.0, desired_length=55.0,
)
_PLUS = SkirtMeasurementProfile(
    waist=95.0, hip=120.0, hip_depth=24.0, desired_length=80.0,
)


# ---------------------------------------------------------------------------
# SkirtMeasurementProfile validation (task 4.2)
# ---------------------------------------------------------------------------


def test_skirt_profile_valid_passes() -> None:
    """Valid profile returns no errors."""
    assert _STANDARD.validate() == []


def test_skirt_profile_waist_below_range() -> None:
    bad = SkirtMeasurementProfile(
        waist=40.0, hip=98.0, hip_depth=20.0, desired_length=70.0,
    )
    errors = bad.validate()
    assert any("waist" in e for e in errors)


def test_skirt_profile_waist_above_range() -> None:
    bad = SkirtMeasurementProfile(
        waist=180.0, hip=98.0, hip_depth=20.0, desired_length=70.0,
    )
    errors = bad.validate()
    assert any("waist" in e for e in errors)


def test_skirt_profile_hip_below_range() -> None:
    bad = SkirtMeasurementProfile(
        waist=73.5, hip=50.0, hip_depth=20.0, desired_length=70.0,
    )
    errors = bad.validate()
    assert any("hip" in e and "hip_depth" not in e for e in errors)


def test_skirt_profile_hip_depth_below_range() -> None:
    bad = SkirtMeasurementProfile(
        waist=73.5, hip=98.0, hip_depth=10.0, desired_length=70.0,
    )
    errors = bad.validate()
    assert any("hip_depth" in e for e in errors)


def test_skirt_profile_hip_depth_above_range() -> None:
    bad = SkirtMeasurementProfile(
        waist=73.5, hip=98.0, hip_depth=35.0, desired_length=70.0,
    )
    errors = bad.validate()
    assert any("hip_depth" in e for e in errors)


def test_skirt_profile_desired_length_below_range() -> None:
    bad = SkirtMeasurementProfile(
        waist=73.5, hip=98.0, hip_depth=20.0, desired_length=30.0,
    )
    errors = bad.validate()
    assert any("desired_length" in e for e in errors)


def test_skirt_profile_desired_length_above_range() -> None:
    bad = SkirtMeasurementProfile(
        waist=73.5, hip=98.0, hip_depth=20.0, desired_length=140.0,
    )
    errors = bad.validate()
    assert any("desired_length" in e for e in errors)


def test_skirt_profile_boundary_low() -> None:
    """Boundary values at range minimums should pass."""
    boundary = SkirtMeasurementProfile(
        waist=50.0, hip=60.0, hip_depth=15.0, desired_length=40.0,
    )
    assert boundary.validate() == []


def test_skirt_profile_boundary_high() -> None:
    """Boundary values at range maximums should pass."""
    boundary = SkirtMeasurementProfile(
        waist=170.0, hip=180.0, hip_depth=30.0, desired_length=130.0,
    )
    assert boundary.validate() == []


def test_skirt_profile_multiple_errors() -> None:
    """Multiple out-of-range fields produce multiple errors."""
    bad = SkirtMeasurementProfile(
        waist=40.0, hip=50.0, hip_depth=10.0, desired_length=30.0,
    )
    errors = bad.validate()
    assert len(errors) >= 3


# ---------------------------------------------------------------------------
# SkirtGenerator unit tests (task 4.5)
# ---------------------------------------------------------------------------


def test_skirt_generator_produces_two_pieces() -> None:
    """Standard profile produces exactly 2 pieces."""
    pieces = _generator.generate(_STANDARD)
    assert len(pieces) == 2


def test_skirt_generator_piece_ids() -> None:
    """Pieces have correct IDs: front_skirt and back_skirt."""
    pieces = _generator.generate(_STANDARD)
    assert pieces[0].piece_id == "front_skirt"
    assert pieces[1].piece_id == "back_skirt"


def test_skirt_generator_closed_outlines() -> None:
    """Each piece has a closed outline (first == last point)."""
    for piece in _generator.generate(_STANDARD):
        assert piece.outline[0] == piece.outline[-1]


def test_skirt_generator_seam_lines_present() -> None:
    """Each piece has at least 4 seam lines."""
    for piece in _generator.generate(_STANDARD):
        assert len(piece.seam_lines) >= 4


def test_skirt_generator_grain_line_vertical() -> None:
    """Grain line is vertical (same x, different y)."""
    for piece in _generator.generate(_STANDARD):
        gl = piece.grain_line
        assert gl.start.x == gl.end.x
        assert gl.start.y != gl.end.y


def test_skirt_generator_notch_marks_present() -> None:
    """Each piece has at least 2 notch marks (waist + hip)."""
    for piece in _generator.generate(_STANDARD):
        assert len(piece.notch_marks) >= 2


def test_skirt_generator_seam_allowance() -> None:
    """Seam allowance is the default 1.5 cm."""
    for piece in _generator.generate(_STANDARD):
        assert piece.seam_allowance == SkirtGenerator.DEFAULT_SEAM_ALLOWANCE


def test_skirt_generator_has_darts() -> None:
    """Front has 1 dart, back has 2 darts."""
    pieces = _generator.generate(_STANDARD)
    assert len(pieces[0].darts) == 1   # front: 1 dart
    assert len(pieces[1].darts) == 2   # back: 2 darts


def test_skirt_generator_dart_scales_with_differential() -> None:
    """Larger waist-hip differential produces larger dart angle."""
    small_diff = SkirtMeasurementProfile(
        waist=90.0, hip=98.0, hip_depth=20.0, desired_length=70.0,
    )
    large_diff = SkirtMeasurementProfile(
        waist=65.0, hip=98.0, hip_depth=20.0, desired_length=70.0,
    )
    small_pieces = _generator.generate(small_diff)
    large_pieces = _generator.generate(large_diff)

    # Compare front dart angles
    small_angle = small_pieces[0].darts[0].angle
    large_angle = large_pieces[0].darts[0].angle
    assert large_angle > small_angle


def test_skirt_generator_hem_flare_symmetric() -> None:
    """Front and back hem widths are equal (measured at max y)."""
    pieces = _generator.generate(_STANDARD)

    def hem_width(outline: tuple) -> float:
        max_y = max(p.y for p in outline)
        hem_pts = [p for p in outline if abs(p.y - max_y) < 1.0]
        if len(hem_pts) < 2:
            return 0.0
        xs = [p.x for p in hem_pts]
        return max(xs) - min(xs)

    assert abs(hem_width(pieces[0].outline) - hem_width(pieces[1].outline)) < 0.01


def test_skirt_generator_invalid_profile_raises() -> None:
    """Out-of-range profile raises ValueError."""
    bad = SkirtMeasurementProfile(
        waist=40.0, hip=50.0, hip_depth=10.0, desired_length=30.0,
    )
    with pytest.raises(ValueError, match="Invalid skirt profile"):
        _generator.generate(bad)


def test_skirt_generator_all_profiles() -> None:
    """Generator works for standard, petite, and plus profiles."""
    for profile in (_STANDARD, _PETITE, _PLUS):
        pieces = _generator.generate(profile)
        assert len(pieces) == 2
        for piece in pieces:
            assert piece.outline[0] == piece.outline[-1]
            assert len(piece.darts) >= 1
            assert len(piece.seam_lines) >= 4
