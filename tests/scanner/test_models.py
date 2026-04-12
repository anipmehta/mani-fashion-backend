"""Unit tests for scanner models: ScanResult, GarmentHint, protocol."""
from __future__ import annotations

import pytest

from agentic_pattern_engine.scanner.models import GarmentHint, ScanResult
from agentic_pattern_engine.scanner.protocol import ScannerAdapter
from agentic_pattern_engine.scanner.adapters import (
    GenericAdapter,
    ThreeDLookAdapter,
)

# ── Test data constants ─────────────────────────────────────────────────
SAMPLE_MEASUREMENT_VALUE = 90.0
CONFIDENCE_VALUE = 0.95
SOURCE_UNIT_CM = "cm"
SCANNER_TYPE_TEST = "test"


# ── GarmentHint enum ────────────────────────────────────────────────────

def test_scanner_models_garment_hint_values() -> None:
    assert GarmentHint.BODICE_ONLY.value == "bodice_only"
    assert GarmentHint.SKIRT_ONLY.value == "skirt_only"
    assert GarmentHint.BOTH.value == "both"
    assert GarmentHint.INSUFFICIENT.value == "insufficient"


def test_scanner_models_garment_hint_member_count() -> None:
    assert len(GarmentHint) == 4


# ── ScanResult ──────────────────────────────────────────────────────────

def test_scanner_models_scan_result_frozen() -> None:
    sr = ScanResult(
        measurements={"chest": SAMPLE_MEASUREMENT_VALUE},
        source_unit=SOURCE_UNIT_CM,
        scanner_type=SCANNER_TYPE_TEST,
        garment_hints=GarmentHint.INSUFFICIENT,
        raw_data={"chest": SAMPLE_MEASUREMENT_VALUE},
    )
    with pytest.raises(AttributeError):
        sr.source_unit = "in"  # type: ignore[misc]


def test_scanner_models_scan_result_default_confidence() -> None:
    sr = ScanResult(
        measurements={},
        source_unit=SOURCE_UNIT_CM,
        scanner_type=SCANNER_TYPE_TEST,
        garment_hints=GarmentHint.INSUFFICIENT,
        raw_data={"x": 1},
    )
    assert sr.confidence_scores is None


def test_scanner_models_scan_result_with_confidence() -> None:
    sr = ScanResult(
        measurements={"chest": SAMPLE_MEASUREMENT_VALUE},
        source_unit=SOURCE_UNIT_CM,
        scanner_type=SCANNER_TYPE_TEST,
        garment_hints=GarmentHint.INSUFFICIENT,
        raw_data={"chest": SAMPLE_MEASUREMENT_VALUE},
        confidence_scores={"chest": CONFIDENCE_VALUE},
    )
    assert sr.confidence_scores == {"chest": CONFIDENCE_VALUE}


# ── ScannerAdapter protocol conformance ─────────────────────────────────

def test_scanner_models_threedlook_satisfies_protocol() -> None:
    assert isinstance(ThreeDLookAdapter(), ScannerAdapter)


def test_scanner_models_generic_satisfies_protocol() -> None:
    assert isinstance(GenericAdapter(), ScannerAdapter)
