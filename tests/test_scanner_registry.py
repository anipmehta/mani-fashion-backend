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

FIXTURES = Path(__file__).parent / "fixtures"


# ── ordering ────────────────────────────────────────────────────────────

def test_scanner_registry_default_order() -> None:
    reg = AdapterRegistry()
    adapters = reg.adapters
    assert isinstance(adapters[0], ThreeDLookAdapter)
    assert isinstance(adapters[1], GenericAdapter)
    assert len(adapters) == 2


# ── parse dispatching ──────────────────────────────────────────────────

def test_scanner_registry_dispatches_to_3dlook() -> None:
    reg = AdapterRegistry()
    result = reg.parse({"bust_girth": 88.0, "waist_girth": 72.0})
    assert result.scanner_type == "3dlook"


def test_scanner_registry_dispatches_to_generic() -> None:
    reg = AdapterRegistry()
    result = reg.parse({"waist": 72.0, "hip": 96.0})
    assert result.scanner_type == "generic"


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
    assert adapters[0].scanner_name == "3dlook"
    assert adapters[1].scanner_name == "dummy"
    assert adapters[2].scanner_name == "generic"


def test_scanner_registry_registered_adapter_used() -> None:
    reg = AdapterRegistry()

    class DummyAdapter:
        @property
        def scanner_name(self) -> str:
            return "dummy"

        def can_handle(self, data: dict) -> bool:
            return "dummy_field" in data

        def parse(self, data: dict) -> ScanResult:
            return ScanResult(
                measurements={"waist": 70.0},
                source_unit="cm",
                scanner_type="dummy",
                garment_hints=GarmentHint.INSUFFICIENT,
                raw_data=data,
            )

    reg.register(DummyAdapter())
    result = reg.parse({"dummy_field": 1})
    assert result.scanner_type == "dummy"


# ── auto-detection with fixtures ────────────────────────────────────────

def test_scanner_registry_auto_detect_3dlook_full(self=None) -> None:
    reg = AdapterRegistry()
    with open(FIXTURES / "3dlook_full_body.json") as f:
        data = json.load(f)
    result = reg.parse(data)
    assert result.scanner_type == "3dlook"
    assert result.garment_hints == GarmentHint.BOTH


def test_scanner_registry_auto_detect_generic(self=None) -> None:
    reg = AdapterRegistry()
    with open(FIXTURES / "generic_mani.json") as f:
        data = json.load(f)
    result = reg.parse(data)
    assert result.scanner_type == "generic"
    assert result.garment_hints == GarmentHint.BOTH


def test_scanner_registry_auto_detect_3dlook_inches() -> None:
    reg = AdapterRegistry()
    with open(FIXTURES / "3dlook_inches.json") as f:
        data = json.load(f)
    result = reg.parse(data)
    assert result.scanner_type == "3dlook"
    assert result.source_unit == "in"
