"""Unit tests for agentic_pattern_engine.scanner.profile_converter."""
from __future__ import annotations

import pytest

from agentic_pattern_engine.models import (
    MeasurementProfile,
    SkirtMeasurementProfile,
)
from agentic_pattern_engine.scanner.adapters import GenericAdapter
from agentic_pattern_engine.scanner.models import GarmentHint, ScanResult
from agentic_pattern_engine.scanner.profile_converter import (
    scan_result_to_bodice_profile,
    scan_result_to_dict,
    scan_result_to_skirt_profile,
)

# ── Helpers ─────────────────────────────────────────────────────────────

# Valid measurements within all validation ranges
_BOTH_MEASUREMENTS: dict[str, float] = {
    "chest": 88.0,
    "waist": 72.0,
    "hip": 96.0,
    "shoulder_width": 40.0,
    "torso_length": 42.0,
    "hip_depth": 20.0,
    "desired_length": 60.0,
}

_BODICE_ONLY_MEASUREMENTS: dict[str, float] = {
    "chest": 88.0,
    "waist": 72.0,
    "hip": 96.0,
    "shoulder_width": 40.0,
    "torso_length": 42.0,
}

_SKIRT_ONLY_MEASUREMENTS: dict[str, float] = {
    "waist": 72.0,
    "hip": 96.0,
    "hip_depth": 20.0,
    "desired_length": 60.0,
}


def _make_scan_result(
    measurements: dict[str, float],
    hints: GarmentHint,
    scanner_type: str = "3dlook",
) -> ScanResult:
    return ScanResult(
        measurements=measurements,
        source_unit="cm",
        scanner_type=scanner_type,
        garment_hints=hints,
        raw_data={"test": True},
    )


# ── Bodice conversion — valid inputs ───────────────────────────────────

def test_profile_converter_bodice_from_both_hints() -> None:
    result = _make_scan_result(_BOTH_MEASUREMENTS, GarmentHint.BOTH)
    profile = scan_result_to_bodice_profile(result)
    assert isinstance(profile, MeasurementProfile)
    assert profile.chest == 88.0
    assert profile.waist == 72.0
    assert profile.hip == 96.0
    assert profile.shoulder_width == 40.0
    assert profile.torso_length == 42.0


def test_profile_converter_bodice_from_bodice_only_hints() -> None:
    result = _make_scan_result(
        _BODICE_ONLY_MEASUREMENTS, GarmentHint.BODICE_ONLY,
    )
    profile = scan_result_to_bodice_profile(result)
    assert isinstance(profile, MeasurementProfile)
    assert profile.chest == 88.0


# ── Skirt conversion — valid inputs ────────────────────────────────────

def test_profile_converter_skirt_from_both_hints() -> None:
    result = _make_scan_result(_BOTH_MEASUREMENTS, GarmentHint.BOTH)
    profile = scan_result_to_skirt_profile(result)
    assert isinstance(profile, SkirtMeasurementProfile)
    assert profile.waist == 72.0
    assert profile.hip == 96.0
    assert profile.hip_depth == 20.0
    assert profile.desired_length == 60.0


def test_profile_converter_skirt_from_skirt_only_hints() -> None:
    result = _make_scan_result(
        _SKIRT_ONLY_MEASUREMENTS, GarmentHint.SKIRT_ONLY,
    )
    profile = scan_result_to_skirt_profile(result)
    assert isinstance(profile, SkirtMeasurementProfile)
    assert profile.waist == 72.0


# ── Incompatible garment hints ─────────────────────────────────────────

def test_profile_converter_bodice_raises_for_skirt_only() -> None:
    result = _make_scan_result(
        _SKIRT_ONLY_MEASUREMENTS, GarmentHint.SKIRT_ONLY,
    )
    with pytest.raises(ValueError, match="incompatible with bodice"):
        scan_result_to_bodice_profile(result)


def test_profile_converter_skirt_raises_for_bodice_only() -> None:
    result = _make_scan_result(
        _BODICE_ONLY_MEASUREMENTS, GarmentHint.BODICE_ONLY,
    )
    with pytest.raises(ValueError, match="incompatible with skirt"):
        scan_result_to_skirt_profile(result)


def test_profile_converter_bodice_raises_for_insufficient() -> None:
    result = _make_scan_result(
        {"waist": 72.0}, GarmentHint.INSUFFICIENT,
    )
    with pytest.raises(ValueError, match="incompatible with bodice"):
        scan_result_to_bodice_profile(result)


def test_profile_converter_skirt_raises_for_insufficient() -> None:
    result = _make_scan_result(
        {"waist": 72.0}, GarmentHint.INSUFFICIENT,
    )
    with pytest.raises(ValueError, match="incompatible with skirt"):
        scan_result_to_skirt_profile(result)


# ── Missing required fields ────────────────────────────────────────────

def test_profile_converter_bodice_raises_missing_field() -> None:
    """Remove shoulder_width — should list it as missing."""
    measurements = {
        k: v for k, v in _BODICE_ONLY_MEASUREMENTS.items()
        if k != "shoulder_width"
    }
    result = _make_scan_result(measurements, GarmentHint.BOTH)
    with pytest.raises(ValueError, match="Missing required bodice"):
        scan_result_to_bodice_profile(result)


def test_profile_converter_skirt_raises_missing_field() -> None:
    """Remove hip_depth — should list it as missing."""
    measurements = {
        k: v for k, v in _SKIRT_ONLY_MEASUREMENTS.items()
        if k != "hip_depth"
    }
    result = _make_scan_result(measurements, GarmentHint.BOTH)
    with pytest.raises(ValueError, match="Missing required skirt"):
        scan_result_to_skirt_profile(result)


# ── scan_result_to_dict ────────────────────────────────────────────────

def test_profile_converter_to_dict_structure() -> None:
    result = _make_scan_result(_BOTH_MEASUREMENTS, GarmentHint.BOTH)
    d = scan_result_to_dict(result)
    assert set(d.keys()) == {
        "measurements", "source_unit", "scanner_type",
        "garment_hints", "raw_data", "confidence_scores",
    }
    assert d["source_unit"] == "cm"
    assert d["scanner_type"] == "3dlook"
    assert d["garment_hints"] == "both"
    assert d["confidence_scores"] is None
    assert d["measurements"]["chest"] == 88.0


# ── Round-trip: to_dict → GenericAdapter.parse ─────────────────────────

def test_profile_converter_dict_round_trip() -> None:
    """Serialize via to_dict, then parse back through GenericAdapter."""
    original = _make_scan_result(_BOTH_MEASUREMENTS, GarmentHint.BOTH)
    d = scan_result_to_dict(original)
    # GenericAdapter expects flat dict with MANI field names
    flat = dict(d["measurements"])
    flat["units"] = d["source_unit"]
    adapter = GenericAdapter()
    assert adapter.can_handle(flat)
    reparsed = adapter.parse(flat)
    for key, val in original.measurements.items():
        assert reparsed.measurements[key] == pytest.approx(val, abs=0.01)


# ── Validation errors propagate ────────────────────────────────────────

def test_profile_converter_bodice_validation_error_out_of_range() -> None:
    """chest=999 is outside [60, 180] — validate() should catch it."""
    measurements = dict(_BODICE_ONLY_MEASUREMENTS)
    measurements["chest"] = 999.0
    result = _make_scan_result(measurements, GarmentHint.BODICE_ONLY)
    with pytest.raises(ValueError, match="validation failed"):
        scan_result_to_bodice_profile(result)


def test_profile_converter_skirt_validation_error_out_of_range() -> None:
    """hip_depth=999 is outside [15, 30] — validate() should catch it."""
    measurements = dict(_SKIRT_ONLY_MEASUREMENTS)
    measurements["hip_depth"] = 999.0
    result = _make_scan_result(measurements, GarmentHint.SKIRT_ONLY)
    with pytest.raises(ValueError, match="validation failed"):
        scan_result_to_skirt_profile(result)
