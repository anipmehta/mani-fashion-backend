"""Unit tests for AdapterRegistry."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_pattern_engine.scanner.adapters import (
    GenericAdapter,
    ThreeDLookAdapter,
)
from agentic_pattern_engine.scanner.models import GarmentHint, ScanResult
from agentic_pattern_engine.scanner.registry import AdapterRegistry

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

# ── Test data constants ─────────────────────────────────────────────────
CHEST_CM = 88.0
WAIST_CM = 72.0
HIP_CM = 96.0
DUMMY_WAIST = 70.0


# ── ordering ────────────────────────────────────────────────────────────

def test_scanner_registry_default_order() -> None:
    reg = AdapterRegistry()
    adapters = reg.adapters
    assert len(adapters) == 2
    assert isinstance(adapters[0], ThreeDLookAdapter)
    assert isinstance(adapters[1], GenericAdapter)


# ── parse dispatching ──────────────────────────────────────────────────

def test_scanner_registry_dispatches_to_3dlook() -> None:
    reg = AdapterRegistry()
    result = reg.parse({"bust_girth": CHEST_CM, "waist_girth": WAIST_CM})
    assert result.scanner_type == ThreeDLookAdapter().scanner_name


def test_scanner_registry_dispatches_to_generic() -> None:
    reg = AdapterRegistry()
    result = reg.parse({"waist": WAIST_CM, "hip": HIP_CM})
    assert result.scanner_type == GenericAdapter().scanner_name


def test_scanner_registry_raises_on_no_match() -> None:
    reg = AdapterRegistry()
    with pytest.raises(ValueError, match="not recognized"):
        reg.parse({"random_field": 42})


# ── register ────────────────────────────────────────────────────────────

def test_scanner_registry_register_inserts_before_generic() -> None:
    reg = AdapterRegistry()

    class DummyAdapter:
        @property
        def scanner_name(self) -> str:
            return "dummy"

        def can_handle(self, data: dict) -> bool:
            return "dummy_field" in data

        def parse(self, data: dict) -> ScanResult:
            return ScanResult(
                measurements={},
                source_unit="cm",
                scanner_type="dummy",
                garment_hints=GarmentHint.INSUFFICIENT,
                raw_data=data,
            )

    reg.register(DummyAdapter())
    adapters = reg.adapters
    assert len(adapters) == 3
    assert adapters[1].scanner_name == "dummy"
    assert isinstance(adapters[2], GenericAdapter)

    # Verify the registered adapter is actually used
    result = reg.parse({"dummy_field": 1})
    assert result.scanner_type == "dummy"


# ── auto-detection with fixtures ────────────────────────────────────────

def test_scanner_registry_auto_detect_3dlook_full() -> None:
    reg = AdapterRegistry()
    with open(FIXTURES / "3dlook_full_body.json") as f:
        data = json.load(f)
    result = reg.parse(data)
    assert result.scanner_type == ThreeDLookAdapter().scanner_name
    assert result.garment_hints == GarmentHint.BOTH


def test_scanner_registry_auto_detect_generic() -> None:
    reg = AdapterRegistry()
    with open(FIXTURES / "generic_mani.json") as f:
        data = json.load(f)
    result = reg.parse(data)
    assert result.scanner_type == GenericAdapter().scanner_name
    assert result.garment_hints == GarmentHint.BOTH
