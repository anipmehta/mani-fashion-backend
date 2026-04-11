"""Unit tests for agentic_pattern_engine.units — unit converter."""
from __future__ import annotations

import pytest

from agentic_pattern_engine.units import (
    cm_to_inches,
    convert_measurements,
    inches_to_cm,
)


# ── inches_to_cm ────────────────────────────────────────────────────────

def test_units_inches_to_cm_known_value() -> None:
    assert inches_to_cm(1.0) == pytest.approx(2.54)


def test_units_inches_to_cm_zero() -> None:
    assert inches_to_cm(0.0) == 0.0


def test_units_inches_to_cm_large_value() -> None:
    assert inches_to_cm(100.0) == pytest.approx(254.0)


# ── cm_to_inches ────────────────────────────────────────────────────────

def test_units_cm_to_inches_known_value() -> None:
    assert cm_to_inches(2.54) == pytest.approx(1.0)


def test_units_cm_to_inches_zero() -> None:
    assert cm_to_inches(0.0) == 0.0


# ── round-trip ──────────────────────────────────────────────────────────

def test_units_round_trip_inches_cm_inches() -> None:
    original = 36.5
    assert cm_to_inches(inches_to_cm(original)) == pytest.approx(
        original, abs=0.01
    )


def test_units_round_trip_cm_inches_cm() -> None:
    original = 92.0
    assert inches_to_cm(cm_to_inches(original)) == pytest.approx(
        original, abs=0.01
    )


# ── convert_measurements ────────────────────────────────────────────────

def test_units_convert_measurements_inches() -> None:
    m = {"chest": 36.0, "waist": 28.0}
    result = convert_measurements(m, "in")
    assert result["chest"] == pytest.approx(36.0 * 2.54)
    assert result["waist"] == pytest.approx(28.0 * 2.54)


def test_units_convert_measurements_inches_long_form() -> None:
    m = {"hip": 40.0}
    result = convert_measurements(m, "inches")
    assert result["hip"] == pytest.approx(40.0 * 2.54)


def test_units_convert_measurements_cm_passthrough() -> None:
    m = {"chest": 90.0}
    result = convert_measurements(m, "cm")
    assert result["chest"] == 90.0


def test_units_convert_measurements_centimeters_passthrough() -> None:
    m = {"chest": 90.0}
    result = convert_measurements(m, "centimeters")
    assert result["chest"] == 90.0


def test_units_convert_measurements_absent_unit_passthrough() -> None:
    m = {"chest": 90.0}
    result = convert_measurements(m, "")
    assert result["chest"] == 90.0


def test_units_convert_measurements_default_passthrough() -> None:
    """No source_unit argument → default to cm (pass through)."""
    m = {"chest": 90.0}
    result = convert_measurements(m)
    assert result["chest"] == 90.0


def test_units_convert_measurements_returns_new_dict() -> None:
    m = {"chest": 90.0}
    result = convert_measurements(m, "cm")
    assert result is not m
