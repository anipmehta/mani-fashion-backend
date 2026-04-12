"""Unit tests for ThreeDLookAdapter and GenericAdapter."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_pattern_engine.scanner.adapters import (
    BODICE_FIELDS,
    SKIRT_FIELDS,
    GenericAdapter,
    ThreeDLookAdapter,
)
from agentic_pattern_engine.scanner.models import GarmentHint

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

# ── Test data constants ─────────────────────────────────────────────────
CHEST_CM = 88.0
WAIST_CM = 72.0
HIP_CM = 96.0
SHOULDER_WIDTH_CM = 40.0
TORSO_LENGTH_CM = 42.0
HIP_DEPTH_CM = 20.0
DESIRED_LENGTH_CM = 60.0

BUST_GIRTH_INCHES = 34.65

# Full 3DLOOK payload covering all MANI fields
THREEDLOOK_FULL_BODY: dict[str, float] = {
    "bust_girth": CHEST_CM,
    "waist_girth": WAIST_CM,
    "hip_girth": HIP_CM,
    "across_shoulder": SHOULDER_WIDTH_CM,
    "back_length": TORSO_LENGTH_CM,
    "hip_depth": HIP_DEPTH_CM,
    "outseam": DESIRED_LENGTH_CM,
}

# Bodice-only subset (no skirt fields)
THREEDLOOK_BODICE_ONLY: dict[str, float] = {
    "bust_girth": CHEST_CM,
    "waist_girth": WAIST_CM,
    "hip_girth": HIP_CM,
    "across_shoulder": SHOULDER_WIDTH_CM,
    "back_length": TORSO_LENGTH_CM,
}

# Skirt-only subset (no bodice-exclusive fields)
THREEDLOOK_SKIRT_ONLY: dict[str, float] = {
    "waist_girth": WAIST_CM,
    "hip_girth": HIP_CM,
    "hip_depth": HIP_DEPTH_CM,
    "outseam": DESIRED_LENGTH_CM,
}

# Generic adapter payloads (MANI field names)
GENERIC_BOTH: dict[str, float] = {
    "chest": 90.0,
    "waist": 74.0,
    "hip": 98.0,
    "shoulder_width": 41.0,
    "torso_length": 43.0,
    "hip_depth": 21.0,
    "desired_length": 58.0,
}

GENERIC_MINIMAL: dict[str, float] = {
    "waist": WAIST_CM,
    "hip": HIP_CM,
}


# ═══════════════════════════════════════════════════════════════════════
# ThreeDLookAdapter — can_handle
# ═══════════════════════════════════════════════════════════════════════

class TestThreeDLookCanHandle:

    def test_recognises_bust_girth(self) -> None:
        adapter = ThreeDLookAdapter()
        assert adapter.can_handle({"bust_girth": CHEST_CM}) is True

    def test_recognises_waist_girth(self) -> None:
        adapter = ThreeDLookAdapter()
        assert adapter.can_handle({"waist_girth": WAIST_CM}) is True

    def test_recognises_source_field(self) -> None:
        adapter = ThreeDLookAdapter()
        assert adapter.can_handle({"source": "3DLOOK_v2"}) is True

    def test_rejects_generic_payload(self) -> None:
        adapter = ThreeDLookAdapter()
        assert adapter.can_handle(GENERIC_MINIMAL) is False

    def test_rejects_empty(self) -> None:
        adapter = ThreeDLookAdapter()
        assert adapter.can_handle({}) is False


# ═══════════════════════════════════════════════════════════════════════
# ThreeDLookAdapter — field mapping (one primary + one secondary alias)
# ═══════════════════════════════════════════════════════════════════════

class TestThreeDLookFieldMapping:

    def test_primary_alias_maps_all_fields(self) -> None:
        """All primary aliases map correctly in a single parse call."""
        adapter = ThreeDLookAdapter()
        result = adapter.parse(THREEDLOOK_FULL_BODY)
        assert result.measurements["chest"] == pytest.approx(CHEST_CM)
        assert result.measurements["waist"] == pytest.approx(WAIST_CM)
        assert result.measurements["hip"] == pytest.approx(HIP_CM)
        assert result.measurements["shoulder_width"] == pytest.approx(SHOULDER_WIDTH_CM)
        assert result.measurements["torso_length"] == pytest.approx(TORSO_LENGTH_CM)
        assert result.measurements["hip_depth"] == pytest.approx(HIP_DEPTH_CM)
        assert result.measurements["desired_length"] == pytest.approx(DESIRED_LENGTH_CM)

    def test_secondary_aliases_map_correctly(self) -> None:
        """Secondary aliases (chest, natural_waist, hips, etc.) also work."""
        adapter = ThreeDLookAdapter()
        data = {
            "chest": CHEST_CM,
            "natural_waist": WAIST_CM,
            "hips": HIP_CM,
            "shoulder_width": SHOULDER_WIDTH_CM,
            "center_back_length": TORSO_LENGTH_CM,
            "waist_to_hip": HIP_DEPTH_CM,
            "side_seam_length": DESIRED_LENGTH_CM,
        }
        result = adapter.parse(data)
        assert result.measurements["chest"] == pytest.approx(CHEST_CM)
        assert result.measurements["waist"] == pytest.approx(WAIST_CM)
        assert result.measurements["hip"] == pytest.approx(HIP_CM)

    def test_primary_alias_takes_priority(self) -> None:
        """When both primary and secondary alias present, primary wins."""
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"bust_girth": CHEST_CM, "chest": 99.0})
        assert result.measurements["chest"] == pytest.approx(CHEST_CM)


# ═══════════════════════════════════════════════════════════════════════
# ThreeDLookAdapter — missing fields & metadata
# ═══════════════════════════════════════════════════════════════════════

class TestThreeDLookBehaviour:

    def test_missing_fields_omitted(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"bust_girth": CHEST_CM})
        assert "waist" not in result.measurements

    def test_empty_payload_gives_empty_measurements(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({})
        assert result.measurements == {}

    def test_scanner_type_is_3dlook(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"bust_girth": CHEST_CM})
        assert result.scanner_type == ThreeDLookAdapter().scanner_name

    def test_raw_data_preserved(self) -> None:
        adapter = ThreeDLookAdapter()
        data = {"bust_girth": CHEST_CM, "extra_field": "hello"}
        result = adapter.parse(data)
        assert result.raw_data == data

    def test_inch_conversion(self) -> None:
        adapter = ThreeDLookAdapter()
        data = {"bust_girth": BUST_GIRTH_INCHES, "units": "in"}
        result = adapter.parse(data)
        assert result.measurements["chest"] == pytest.approx(BUST_GIRTH_INCHES * 2.54)
        assert result.source_unit == "in"


# ═══════════════════════════════════════════════════════════════════════
# ThreeDLookAdapter — garment hint detection
# ═══════════════════════════════════════════════════════════════════════

class TestThreeDLookGarmentHints:

    def test_hint_both(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse(THREEDLOOK_FULL_BODY)
        assert result.garment_hints == GarmentHint.BOTH

    def test_hint_bodice_only(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse(THREEDLOOK_BODICE_ONLY)
        assert result.garment_hints == GarmentHint.BODICE_ONLY

    def test_hint_skirt_only(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse(THREEDLOOK_SKIRT_ONLY)
        assert result.garment_hints == GarmentHint.SKIRT_ONLY

    def test_hint_insufficient(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"waist_girth": WAIST_CM, "hip_girth": HIP_CM})
        assert result.garment_hints == GarmentHint.INSUFFICIENT


# ═══════════════════════════════════════════════════════════════════════
# ThreeDLookAdapter — fixture files
# ═══════════════════════════════════════════════════════════════════════

class TestThreeDLookFixtures:

    def test_full_body_fixture(self) -> None:
        with open(FIXTURES / "3dlook_full_body.json") as f:
            data = json.load(f)
        adapter = ThreeDLookAdapter()
        result = adapter.parse(data)
        assert result.garment_hints == GarmentHint.BOTH
        assert result.measurements["chest"] == pytest.approx(CHEST_CM)

    def test_upper_only_fixture(self) -> None:
        with open(FIXTURES / "3dlook_upper_only.json") as f:
            data = json.load(f)
        adapter = ThreeDLookAdapter()
        result = adapter.parse(data)
        assert result.garment_hints == GarmentHint.BODICE_ONLY

    def test_inches_fixture(self) -> None:
        with open(FIXTURES / "3dlook_inches.json") as f:
            data = json.load(f)
        adapter = ThreeDLookAdapter()
        result = adapter.parse(data)
        assert result.source_unit == "in"
        assert result.measurements["chest"] == pytest.approx(
            BUST_GIRTH_INCHES * 2.54, abs=0.1,
        )

    def test_minimal_fixture(self) -> None:
        with open(FIXTURES / "3dlook_minimal.json") as f:
            data = json.load(f)
        adapter = ThreeDLookAdapter()
        result = adapter.parse(data)
        assert result.garment_hints == GarmentHint.INSUFFICIENT


# ═══════════════════════════════════════════════════════════════════════
# GenericAdapter
# ═══════════════════════════════════════════════════════════════════════

class TestGenericAdapter:

    def test_can_handle_waist_and_hip(self) -> None:
        adapter = GenericAdapter()
        assert adapter.can_handle(GENERIC_MINIMAL) is True

    def test_rejects_missing_hip(self) -> None:
        adapter = GenericAdapter()
        assert adapter.can_handle({"waist": WAIST_CM}) is False

    def test_rejects_non_numeric(self) -> None:
        adapter = GenericAdapter()
        assert adapter.can_handle({"waist": "big", "hip": HIP_CM}) is False

    def test_ignores_unknown_keys(self) -> None:
        adapter = GenericAdapter()
        data = {**GENERIC_MINIMAL, "shoe_size": 42, "mood": "happy"}
        result = adapter.parse(data)
        assert "shoe_size" not in result.measurements
        assert "waist" in result.measurements

    def test_scanner_type_is_generic(self) -> None:
        adapter = GenericAdapter()
        result = adapter.parse(GENERIC_MINIMAL)
        assert result.scanner_type == GenericAdapter().scanner_name

    def test_hint_both(self) -> None:
        adapter = GenericAdapter()
        result = adapter.parse(GENERIC_BOTH)
        assert result.garment_hints == GarmentHint.BOTH

    def test_hint_insufficient(self) -> None:
        adapter = GenericAdapter()
        result = adapter.parse(GENERIC_MINIMAL)
        assert result.garment_hints == GarmentHint.INSUFFICIENT

    def test_fixture(self) -> None:
        with open(FIXTURES / "generic_mani.json") as f:
            data = json.load(f)
        adapter = GenericAdapter()
        result = adapter.parse(data)
        assert result.garment_hints == GarmentHint.BOTH
        assert result.measurements["chest"] == pytest.approx(90.0)
