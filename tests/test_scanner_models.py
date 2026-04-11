"""Unit tests for scanner models: ScanResult, GarmentHint, protocol."""
from __future__ import annotations

import pytest

from agentic_pattern_engine.scanner.models import GarmentHint, ScanResult
from agentic_pattern_engine.scanner.protocol import ScannerAdapter
from agentic_pattern_engine.scanner.adapters import (
    GenericAdapter,
    ThreeDLookAdapter,
)


# ── GarmentHint enum ────────────────────────────────────────────────────

def test_scanner_models_garment_hint_values() -> None:
    assert GarmentHint.BODICE_ONLY.value == "bodice_only"
    assert GarmentHint.SKIRT_ONLY.value == "skirt_only"
    assert GarmentHint.BOTH.value == "both"
    assert GarmentHint.INSUFFICIENT.value == "insufficient"


def test_scanner_models_garment_hint_member_count() -> None:
    assert len(GarmentHint) == 4


# ── ScanResult frozen immutability ──────────────────────────────────────

def test_scanner_models_scan_result_frozen() -> None:
    sr = ScanResult(
        measurements={"chest": 90.0},
        source_unit="cm",
        scanner_type="test",
        garment_hints=GarmentHint.INSUFFICIENT,
        raw_data={"chest": 90.0},
    )
    with pytest.raises(AttributeError):
        sr.source_unit = "in"  # type: ignore[misc]


def test_scanner_models_scan_result_default_confidence() -> None:
    sr = ScanResult(
        measurements={},
        source_unit="cm",
        scanner_type="test",
        garment_hints=GarmentHint.INSUFFICIENT,
        raw_data={"x": 1},
    )
    assert sr.confidence_scores is None


def test_scanner_models_scan_result_with_confidence() -> None:
    sr = ScanResult(
        measurements={"chest": 90.0},
        source_unit="cm",
        scanner_type="test",
        garment_hints=GarmentHint.INSUFFICIENT,
        raw_data={"chest": 90.0},
        confidence_scores={"chest": 0.95},
    )
    assert sr.confidence_scores == {"chest": 0.95}


# ── ScannerAdapter protocol conformance ─────────────────────────────────

def test_scanner_models_threedlook_satisfies_protocol() -> None:
    assert isinstance(ThreeDLookAdapter(), ScannerAdapter)


def test_scanner_models_generic_satisfies_protocol() -> None:
    assert isinstance(GenericAdapter(), ScannerAdapter)
