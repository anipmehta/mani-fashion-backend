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
    BODICE_REQUIRED,
    FIELD_CHEST,
    FIELD_DESIRED_LENGTH,
    FIELD_HIP,
    FIELD_HIP_DEPTH,
    FIELD_SHOULDER_WIDTH,
    FIELD_TORSO_LENGTH,
    FIELD_WAIST,
    SKIRT_REQUIRED,
    scan_result_to_bodice_profile,
    scan_result_to_dict,
    scan_result_to_skirt_profile,
)

# ── Test data constants ─────────────────────────────────────────────────
CHEST_CM = 88.0
WAIST_CM = 72.0
HIP_CM = 96.0
SHOULDER_WIDTH_CM = 40.0
TORSO_LENGTH_CM = 42.0
HIP_DEPTH_CM = 20.0
DESIRED_LENGTH_CM = 60.0
OUT_OF_RANGE_VALUE = 999.0

SOURCE_UNIT_CM = "cm"
SCANNER_TYPE_3DLOOK = "3dlook"

_BOTH_MEASUREMENTS: dict[str, float] = {
    FIELD_CHEST: CHEST_CM,
    FIELD_WAIST: WAIST_CM,
    FIELD_HIP: HIP_CM,
    FIELD_SHOULDER_WIDTH: SHOULDER_WIDTH_CM,
    FIELD_TORSO_LENGTH: TORSO_LENGTH_CM,
    FIELD_HIP_DEPTH: HIP_DEPTH_CM,
    FIELD_DESIRED_LENGTH: DESIRED_LENGTH_CM,
}

_BODICE_ONLY_MEASUREMENTS: dict[str, float] = {
    FIELD_CHEST: CHEST_CM,
    FIELD_WAIST: WAIST_CM,
    FIELD_HIP: HIP_CM,
    FIELD_SHOULDER_WIDTH: SHOULDER_WIDTH_CM,
    FIELD_TORSO_LENGTH: TORSO_LENGTH_CM,
}

_SKIRT_ONLY_MEASUREMENTS: dict[str, float] = {
    FIELD_WAIST: WAIST_CM,
    FIELD_HIP: HIP_CM,
    FIELD_HIP_DEPTH: HIP_DEPTH_CM,
    FIELD_DESIRED_LENGTH: DESIRED_LENGTH_CM,
}


def _make_scan_result(
    measurements: dict[str, float],
    hints: GarmentHint,
    scanner_type: str = SCANNER_TYPE_3DLOOK,
) -> ScanResult:
    return ScanResult(
        measurements=measurements,
        source_unit=SOURCE_UNIT_CM,
        scanner_type=scanner_type,
        garment_hints=hints,
        raw_data={"test": True},
    )


# ── Bodice conversion — valid inputs ───────────────────────────────────

def test_profile_converter_bodice_from_both_hints() -> None:
    result = _make_scan_result(_BOTH_MEASUREMENTS, GarmentHint.BOTH)
    profile = scan_result_to_bodice_profile(result)
    assert isinstance(profile, MeasurementProfile)
    assert profile.chest == CHEST_CM
    assert profile.waist == WAIST_CM
    assert profile.hip == HIP_CM
    assert profile.shoulder_width == SHOULDER_WIDTH_CM
    assert profile.torso_length == TORSO_LENGTH_CM


def test_profile_converter_bodice_from_bodice_only_hints() -> None:
    result = _make_scan_result(
        _BODICE_ONLY_MEASUREMENTS, GarmentHint.BODICE_ONLY,
    )
    profile = scan_result_to_bodice_profile(result)
    assert isinstance(profile, MeasurementProfile)
    assert profile.chest == CHEST_CM


# ── Skirt conversion — valid inputs ────────────────────────────────────

def test_profile_converter_skirt_from_both_hints() -> None:
    result = _make_scan_result(_BOTH_MEASUREMENTS, GarmentHint.BOTH)
    profile = scan_result_to_skirt_profile(result)
    assert isinstance(profile, SkirtMeasurementProfile)
    assert profile.waist == WAIST_CM
    assert profile.hip == HIP_CM
    assert profile.hip_depth == HIP_DEPTH_CM
    assert profile.desired_length == DESIRED_LENGTH_CM


def test_profile_converter_skirt_from_skirt_only_hints() -> None:
    result = _make_scan_result(
        _SKIRT_ONLY_MEASUREMENTS, GarmentHint.SKIRT_ONLY,
    )
    profile = scan_result_to_skirt_profile(result)
    assert isinstance(profile, SkirtMeasurementProfile)
    assert profile.waist == WAIST_CM


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


def test_profile_converter_raises_for_insufficient() -> None:
    result = _make_scan_result(
        {FIELD_WAIST: WAIST_CM}, GarmentHint.INSUFFICIENT,
    )
    with pytest.raises(ValueError, match="incompatible with bodice"):
        scan_result_to_bodice_profile(result)
    with pytest.raises(ValueError, match="incompatible with skirt"):
        scan_result_to_skirt_profile(result)


# ── Missing required fields ────────────────────────────────────────────

def test_profile_converter_bodice_raises_missing_field() -> None:
    measurements = {
        k: v for k, v in _BODICE_ONLY_MEASUREMENTS.items()
        if k != FIELD_SHOULDER_WIDTH
    }
    result = _make_scan_result(measurements, GarmentHint.BOTH)
    with pytest.raises(ValueError, match="Missing required bodice"):
        scan_result_to_bodice_profile(result)


def test_profile_converter_skirt_raises_missing_field() -> None:
    measurements = {
        k: v for k, v in _SKIRT_ONLY_MEASUREMENTS.items()
        if k != FIELD_HIP_DEPTH
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
    assert d["source_unit"] == SOURCE_UNIT_CM
    assert d["scanner_type"] == SCANNER_TYPE_3DLOOK
    assert d["garment_hints"] == GarmentHint.BOTH.value
    assert d["confidence_scores"] is None
    assert d["measurements"][FIELD_CHEST] == CHEST_CM


# ── Round-trip: to_dict → GenericAdapter.parse ─────────────────────────

def test_profile_converter_dict_round_trip() -> None:
    original = _make_scan_result(_BOTH_MEASUREMENTS, GarmentHint.BOTH)
    d = scan_result_to_dict(original)
    flat = dict(d["measurements"])
    flat["units"] = d["source_unit"]
    adapter = GenericAdapter()
    assert adapter.can_handle(flat)
    reparsed = adapter.parse(flat)
    for key, val in original.measurements.items():
        assert reparsed.measurements[key] == pytest.approx(val, abs=0.01)


# ── Validation errors propagate ────────────────────────────────────────

def test_profile_converter_bodice_validation_error_out_of_range() -> None:
    measurements = dict(_BODICE_ONLY_MEASUREMENTS)
    measurements[FIELD_CHEST] = OUT_OF_RANGE_VALUE
    result = _make_scan_result(measurements, GarmentHint.BODICE_ONLY)
    with pytest.raises(ValueError, match="validation failed"):
        scan_result_to_bodice_profile(result)


def test_profile_converter_skirt_validation_error_out_of_range() -> None:
    measurements = dict(_SKIRT_ONLY_MEASUREMENTS)
    measurements[FIELD_HIP_DEPTH] = OUT_OF_RANGE_VALUE
    result = _make_scan_result(measurements, GarmentHint.SKIRT_ONLY)
    with pytest.raises(ValueError, match="validation failed"):
        scan_result_to_skirt_profile(result)
