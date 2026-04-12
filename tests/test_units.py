"""Unit tests for agentic_pattern_engine.units — unit converter."""
from __future__ import annotations

import pytest

from agentic_pattern_engine.units import (
    INCHES_TO_CM_FACTOR,
    cm_to_inches,
    convert_measurements,
    inches_to_cm,
)

# ── Test data constants ─────────────────────────────────────────────────
ONE_INCH_IN_CM = INCHES_TO_CM_FACTOR  # 2.54
LARGE_INCHES = 100.0
LARGE_CM = LARGE_INCHES * INCHES_TO_CM_FACTOR  # 254.0
ROUND_TRIP_INCHES = 36.5
ROUND_TRIP_CM = 92.0
CHEST_INCHES = 36.0
WAIST_INCHES = 28.0
HIP_INCHES = 40.0
CHEST_CM = 90.0


# ── inches_to_cm ────────────────────────────────────────────────────────

def test_units_inches_to_cm_known_value() -> None:
    assert inches_to_cm(1.0) == pytest.approx(ONE_INCH_IN_CM)


def test_units_inches_to_cm_zero() -> None:
    assert inches_to_cm(0.0) == 0.0


def test_units_inches_to_cm_large_value() -> None:
    assert inches_to_cm(LARGE_INCHES) == pytest.approx(LARGE_CM)


# ── cm_to_inches ────────────────────────────────────────────────────────

def test_units_cm_to_inches_known_value() -> None:
    assert cm_to_inches(ONE_INCH_IN_CM) == pytest.approx(1.0)


def test_units_cm_to_inches_zero() -> None:
    assert cm_to_inches(0.0) == 0.0


# ── round-trip ──────────────────────────────────────────────────────────

def test_units_round_trip_inches_cm_inches() -> None:
    assert cm_to_inches(inches_to_cm(ROUND_TRIP_INCHES)) == pytest.approx(
        ROUND_TRIP_INCHES, abs=0.01,
    )


def test_units_round_trip_cm_inches_cm() -> None:
    assert inches_to_cm(cm_to_inches(ROUND_TRIP_CM)) == pytest.approx(
        ROUND_TRIP_CM, abs=0.01,
    )


# ── convert_measurements ────────────────────────────────────────────────

def test_units_convert_measurements_inches() -> None:
    m = {"chest": CHEST_INCHES, "waist": WAIST_INCHES}
    result = convert_measurements(m, "in")
    assert result["chest"] == pytest.approx(CHEST_INCHES * INCHES_TO_CM_FACTOR)
    assert result["waist"] == pytest.approx(WAIST_INCHES * INCHES_TO_CM_FACTOR)


def test_units_convert_measurements_inches_long_form() -> None:
    m = {"hip": HIP_INCHES}
    result = convert_measurements(m, "inches")
    assert result["hip"] == pytest.approx(HIP_INCHES * INCHES_TO_CM_FACTOR)


def test_units_convert_measurements_cm_passthrough() -> None:
    m = {"chest": CHEST_CM}
    result = convert_measurements(m, "cm")
    assert result["chest"] == CHEST_CM


def test_units_convert_measurements_absent_unit_passthrough() -> None:
    m = {"chest": CHEST_CM}
    result = convert_measurements(m, "")
    assert result["chest"] == CHEST_CM


def test_units_convert_measurements_default_passthrough() -> None:
    m = {"chest": CHEST_CM}
    result = convert_measurements(m)
    assert result["chest"] == CHEST_CM


def test_units_convert_measurements_returns_new_dict() -> None:
    m = {"chest": CHEST_CM}
    result = convert_measurements(m, "cm")
    assert result is not m
