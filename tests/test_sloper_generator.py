"""Property-based tests for the Sloper Generator.

Tests Properties 1 and 2 from the Agentic Pattern Engine design document.
"""

from __future__ import annotations

from hypothesis import given, settings

from agentic_pattern_engine.models import MeasurementProfile
from agentic_pattern_engine.sloper_generator import ParsonsSloperGenerator

# Import strategies from conftest (auto-discovered by pytest)
from tests.conftest import measurement_profiles


# ---------------------------------------------------------------------------
# Feature: agentic-pattern-engine, Property 1: Sloper generation determinism
# ---------------------------------------------------------------------------

# **Validates: Requirements 1.1, 1.5**


@given(profile=measurement_profiles())
@settings(max_examples=100)
def test_sloper_generation_determinism(profile: MeasurementProfile) -> None:
    """For any valid MeasurementProfile, generate(p) called twice must
    produce identical BodiceSlopers (excluding sloper_id which is uuid)."""
    gen = ParsonsSloperGenerator()
    s1 = gen.generate(profile)
    s2 = gen.generate(profile)

    # Compare everything except sloper_id (which is a fresh uuid each time)
    assert s1.front_bodice == s2.front_bodice
    assert s1.back_bodice == s2.back_bodice
    assert s1.bust_ease == s2.bust_ease
    assert s1.waist_ease == s2.waist_ease


# ---------------------------------------------------------------------------
# Feature: agentic-pattern-engine, Property 2: Sloper structural completeness
# ---------------------------------------------------------------------------

# **Validates: Requirements 1.2, 1.3**


@given(profile=measurement_profiles())
@settings(max_examples=100)
def test_sloper_structural_completeness(profile: MeasurementProfile) -> None:
    """For any valid MeasurementProfile, generated BodiceSloper must have
    proper structure: two pieces, each with closed outline, darts, seam lines,
    grain line, notch marks, positive seam allowance, and positive ease."""
    gen = ParsonsSloperGenerator()
    sloper = gen.generate(profile)

    # Two pieces
    for piece in [sloper.front_bodice, sloper.back_bodice]:
        # Closed outline
        assert piece.outline[0] == piece.outline[-1]
        # Has darts
        assert len(piece.darts) >= 1
        # Has seam lines
        assert len(piece.seam_lines) >= 1
        # Has grain line
        assert piece.grain_line is not None
        # Has notch marks
        assert len(piece.notch_marks) >= 1
        # Positive seam allowance
        assert piece.seam_allowance > 0
        # Non-empty label
        assert len(piece.label) > 0

    # Positive ease
    assert sloper.bust_ease > 0
    assert sloper.waist_ease > 0
