"""ScanResult — immutable container for parsed scan data."""
from __future__ import annotations

from dataclasses import dataclass, field

from agentic_pattern_engine.scanner.models.garment_hint import GarmentHint


@dataclass(frozen=True)
class ScanResult:
    """Immutable container for parsed scan data.

    All measurement values are stored in centimeters regardless of the
    scanner's original output unit.
    """

    measurements: dict[str, float]
    source_unit: str
    scanner_type: str
    garment_hints: GarmentHint
    raw_data: dict = field(repr=False)
    confidence_scores: dict[str, float] | None = None
