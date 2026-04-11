"""Unit tests for ThreeDLookAdapter and GenericAdapter."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_pattern_engine.scanner.adapters import (
    GenericAdapter,
    ThreeDLookAdapter,
)
from agentic_pattern_engine.scanner.models import GarmentHint

FIXTURES = Path(__file__).parent / "fixtures"


# ═══════════════════════════════════════════════════════════════════════
# ThreeDLookAdapter — can_handle
# ═══════════════════════════════════════════════════════════════════════

class TestThreeDLookCanHandle:

    def test_scanner_adapters_3dlook_can_handle_bust_girth(self) -> None:
        adapter = ThreeDLookAdapter()
        assert adapter.can_handle({"bust_girth": 88.0}) is True

    def test_scanner_adapters_3dlook_can_handle_waist_girth(self) -> None:
        adapter = ThreeDLookAdapter()
        assert adapter.can_handle({"waist_girth": 72.0}) is True

    def test_scanner_adapters_3dlook_can_handle_source_field(self) -> None:
        adapter = ThreeDLookAdapter()
        assert adapter.can_handle({"source": "3dlook", "waist": 72}) is True

    def test_scanner_adapters_3dlook_can_handle_source_case(self) -> None:
        adapter = ThreeDLookAdapter()
        assert adapter.can_handle({"source": "3DLOOK_v2"}) is True

    def test_scanner_adapters_3dlook_cannot_handle_generic(self) -> None:
        adapter = ThreeDLookAdapter()
        assert adapter.can_handle({"waist": 72, "hip": 96}) is False

    def test_scanner_adapters_3dlook_cannot_handle_empty(self) -> None:
        adapter = ThreeDLookAdapter()
        assert adapter.can_handle({}) is False


# ═══════════════════════════════════════════════════════════════════════
# ThreeDLookAdapter — field mapping
# ═══════════════════════════════════════════════════════════════════════

class TestThreeDLookFieldMapping:

    def test_scanner_adapters_3dlook_maps_bust_girth_to_chest(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"bust_girth": 88.0, "waist_girth": 72.0})
        assert result.measurements["chest"] == pytest.approx(88.0)

    def test_scanner_adapters_3dlook_maps_waist_girth_to_waist(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"waist_girth": 72.0})
        assert result.measurements["waist"] == pytest.approx(72.0)

    def test_scanner_adapters_3dlook_maps_hip_girth_to_hip(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"hip_girth": 96.0})
        assert result.measurements["hip"] == pytest.approx(96.0)

    def test_scanner_adapters_3dlook_maps_across_shoulder(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"across_shoulder": 40.0})
        assert result.measurements["shoulder_width"] == pytest.approx(40.0)

    def test_scanner_adapters_3dlook_maps_back_length(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"back_length": 42.0})
        assert result.measurements["torso_length"] == pytest.approx(42.0)

    def test_scanner_adapters_3dlook_maps_hip_depth(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"hip_depth": 20.0})
        assert result.measurements["hip_depth"] == pytest.approx(20.0)

    def test_scanner_adapters_3dlook_maps_outseam(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"outseam": 60.0})
        assert result.measurements["desired_length"] == pytest.approx(60.0)

    def test_scanner_adapters_3dlook_secondary_alias_chest(self) -> None:
        """'chest' is the secondary alias for MANI chest field."""
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"chest": 88.0})
        assert result.measurements["chest"] == pytest.approx(88.0)

    def test_scanner_adapters_3dlook_secondary_alias_natural_waist(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"natural_waist": 72.0})
        assert result.measurements["waist"] == pytest.approx(72.0)

    def test_scanner_adapters_3dlook_secondary_alias_hips(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"hips": 96.0})
        assert result.measurements["hip"] == pytest.approx(96.0)

    def test_scanner_adapters_3dlook_secondary_alias_shoulder_width(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"shoulder_width": 40.0})
        assert result.measurements["shoulder_width"] == pytest.approx(40.0)

    def test_scanner_adapters_3dlook_secondary_alias_center_back(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"center_back_length": 42.0})
        assert result.measurements["torso_length"] == pytest.approx(42.0)

    def test_scanner_adapters_3dlook_secondary_alias_waist_to_hip(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"waist_to_hip": 20.0})
        assert result.measurements["hip_depth"] == pytest.approx(20.0)

    def test_scanner_adapters_3dlook_secondary_alias_side_seam(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"side_seam_length": 60.0})
        assert result.measurements["desired_length"] == pytest.approx(60.0)


# ═══════════════════════════════════════════════════════════════════════
# ThreeDLookAdapter — alias priority
# ═══════════════════════════════════════════════════════════════════════

class TestThreeDLookAliasPriority:

    def test_scanner_adapters_3dlook_alias_priority_chest(self) -> None:
        """bust_girth takes priority over chest."""
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"bust_girth": 88.0, "chest": 99.0})
        assert result.measurements["chest"] == pytest.approx(88.0)

    def test_scanner_adapters_3dlook_alias_priority_waist(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"waist_girth": 72.0, "natural_waist": 80.0})
        assert result.measurements["waist"] == pytest.approx(72.0)

    def test_scanner_adapters_3dlook_alias_priority_hip(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"hip_girth": 96.0, "hips": 100.0})
        assert result.measurements["hip"] == pytest.approx(96.0)


# ═══════════════════════════════════════════════════════════════════════
# ThreeDLookAdapter — missing field omission
# ═══════════════════════════════════════════════════════════════════════

class TestThreeDLookMissingFields:

    def test_scanner_adapters_3dlook_missing_field_omitted(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"bust_girth": 88.0})
        assert "waist" not in result.measurements
        assert "hip" not in result.measurements

    def test_scanner_adapters_3dlook_no_default_values(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({})
        assert result.measurements == {}


# ═══════════════════════════════════════════════════════════════════════
# ThreeDLookAdapter — garment hint detection
# ═══════════════════════════════════════════════════════════════════════

class TestThreeDLookGarmentHints:

    def test_scanner_adapters_3dlook_hint_both(self) -> None:
        adapter = ThreeDLookAdapter()
        data = {
            "bust_girth": 88.0, "waist_girth": 72.0, "hip_girth": 96.0,
            "across_shoulder": 40.0, "back_length": 42.0,
            "hip_depth": 20.0, "outseam": 60.0,
        }
        result = adapter.parse(data)
        assert result.garment_hints == GarmentHint.BOTH

    def test_scanner_adapters_3dlook_hint_bodice_only(self) -> None:
        adapter = ThreeDLookAdapter()
        data = {
            "bust_girth": 88.0, "waist_girth": 72.0, "hip_girth": 96.0,
            "across_shoulder": 40.0, "back_length": 42.0,
        }
        result = adapter.parse(data)
        assert result.garment_hints == GarmentHint.BODICE_ONLY

    def test_scanner_adapters_3dlook_hint_skirt_only(self) -> None:
        adapter = ThreeDLookAdapter()
        data = {
            "waist_girth": 72.0, "hip_girth": 96.0,
            "hip_depth": 20.0, "outseam": 60.0,
        }
        result = adapter.parse(data)
        assert result.garment_hints == GarmentHint.SKIRT_ONLY

    def test_scanner_adapters_3dlook_hint_insufficient(self) -> None:
        adapter = ThreeDLookAdapter()
        data = {"waist_girth": 72.0, "hip_girth": 96.0}
        result = adapter.parse(data)
        assert result.garment_hints == GarmentHint.INSUFFICIENT

    def test_scanner_adapters_3dlook_scanner_type(self) -> None:
        adapter = ThreeDLookAdapter()
        result = adapter.parse({"bust_girth": 88.0})
        assert result.scanner_type == "3dlook"

    def test_scanner_adapters_3dlook_raw_data_preserved(self) -> None:
        adapter = ThreeDLookAdapter()
        data = {"bust_girth": 88.0, "extra_field": "hello"}
        result = adapter.parse(data)
        assert result.raw_data == data

    def test_scanner_adapters_3dlook_unit_conversion_inches(self) -> None:
        adapter = ThreeDLookAdapter()
        data = {"bust_girth": 34.65, "units": "in"}
        result = adapter.parse(data)
        assert result.measurements["chest"] == pytest.approx(34.65 * 2.54)
        assert result.source_unit == "in"

    def test_scanner_adapters_3dlook_full_body_fixture(self) -> None:
        with open(FIXTURES / "3dlook_full_body.json") as f:
            data = json.load(f)
        adapter = ThreeDLookAdapter()
        result = adapter.parse(data)
        assert result.garment_hints == GarmentHint.BOTH
        assert result.measurements["chest"] == pytest.approx(88.0)

    def test_scanner_adapters_3dlook_upper_only_fixture(self) -> None:
        with open(FIXTURES / "3dlook_upper_only.json") as f:
            data = json.load(f)
        adapter = ThreeDLookAdapter()
        result = adapter.parse(data)
        assert result.garment_hints == GarmentHint.BODICE_ONLY

    def test_scanner_adapters_3dlook_inches_fixture(self) -> None:
        with open(FIXTURES / "3dlook_inches.json") as f:
            data = json.load(f)
        adapter = ThreeDLookAdapter()
        result = adapter.parse(data)
        assert result.source_unit == "in"
        # Values should be converted to cm
        assert result.measurements["chest"] == pytest.approx(
            34.65 * 2.54, abs=0.1
        )

    def test_scanner_adapters_3dlook_minimal_fixture(self) -> None:
        with open(FIXTURES / "3dlook_minimal.json") as f:
            data = json.load(f)
        adapter = ThreeDLookAdapter()
        result = adapter.parse(data)
        assert result.garment_hints == GarmentHint.INSUFFICIENT


# ═══════════════════════════════════════════════════════════════════════
# GenericAdapter
# ═══════════════════════════════════════════════════════════════════════

class TestGenericAdapter:

    def test_scanner_adapters_generic_can_handle_waist_hip(self) -> None:
        adapter = GenericAdapter()
        assert adapter.can_handle({"waist": 72.0, "hip": 96.0}) is True

    def test_scanner_adapters_generic_cannot_handle_missing_hip(self) -> None:
        adapter = GenericAdapter()
        assert adapter.can_handle({"waist": 72.0}) is False

    def test_scanner_adapters_generic_cannot_handle_missing_waist(self) -> None:
        adapter = GenericAdapter()
        assert adapter.can_handle({"hip": 96.0}) is False

    def test_scanner_adapters_generic_cannot_handle_non_numeric(self) -> None:
        adapter = GenericAdapter()
        assert adapter.can_handle({"waist": "big", "hip": 96.0}) is False

    def test_scanner_adapters_generic_ignores_unknown_keys(self) -> None:
        adapter = GenericAdapter()
        data = {"waist": 72.0, "hip": 96.0, "shoe_size": 42, "mood": "happy"}
        result = adapter.parse(data)
        assert "shoe_size" not in result.measurements
        assert "mood" not in result.measurements
        assert "waist" in result.measurements
        assert "hip" in result.measurements

    def test_scanner_adapters_generic_scanner_type(self) -> None:
        adapter = GenericAdapter()
        result = adapter.parse({"waist": 72.0, "hip": 96.0})
        assert result.scanner_type == "generic"

    def test_scanner_adapters_generic_garment_hint_both(self) -> None:
        adapter = GenericAdapter()
        data = {
            "chest": 90.0, "waist": 74.0, "hip": 98.0,
            "shoulder_width": 41.0, "torso_length": 43.0,
            "hip_depth": 21.0, "desired_length": 58.0,
        }
        result = adapter.parse(data)
        assert result.garment_hints == GarmentHint.BOTH

    def test_scanner_adapters_generic_garment_hint_insufficient(self) -> None:
        adapter = GenericAdapter()
        result = adapter.parse({"waist": 72.0, "hip": 96.0})
        assert result.garment_hints == GarmentHint.INSUFFICIENT

    def test_scanner_adapters_generic_fixture(self) -> None:
        with open(FIXTURES / "generic_mani.json") as f:
            data = json.load(f)
        adapter = GenericAdapter()
        result = adapter.parse(data)
        assert result.garment_hints == GarmentHint.BOTH
        assert result.measurements["chest"] == pytest.approx(90.0)
