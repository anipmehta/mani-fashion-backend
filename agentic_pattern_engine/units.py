"""Shared unit conversion utilities for the MANI pattern engine.

Provides bidirectional conversion between centimeters and inches,
plus a batch converter for measurement dictionaries.
"""
from __future__ import annotations

# Conversion factor: 1 inch = 2.54 cm
INCHES_TO_CM_FACTOR: float = 2.54

# Unit strings recognised as "inches"
_INCH_UNITS: frozenset[str] = frozenset({"in", "inches"})

# Unit strings recognised as "centimeters" (including absent / empty)
_CM_UNITS: frozenset[str] = frozenset({"cm", "centimeters", ""})


def inches_to_cm(value: float) -> float:
    """Convert a measurement from inches to centimeters."""
    return value * INCHES_TO_CM_FACTOR


def cm_to_inches(value: float) -> float:
    """Convert a measurement from centimeters to inches."""
    return value / INCHES_TO_CM_FACTOR


def convert_measurements(
    measurements: dict[str, float],
    source_unit: str = "",
) -> dict[str, float]:
    """Return *measurements* with all values converted to centimeters.

    Recognised *source_unit* values:
    - ``"in"`` / ``"inches"`` → multiply each value by 2.54
    - ``"cm"`` / ``"centimeters"`` / ``""`` (absent) → pass through unchanged
    """
    unit = source_unit.strip().lower()
    if unit in _INCH_UNITS:
        return {k: inches_to_cm(v) for k, v in measurements.items()}
    # cm, centimeters, or absent → no conversion
    return dict(measurements)
