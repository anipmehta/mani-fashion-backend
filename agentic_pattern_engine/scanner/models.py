"""Scanner data models: ScanResult and GarmentHint."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GarmentHint(Enum):
    """Indicates which garment types a scan's measurements can support."""

    BODICE_ONLY = "bodice_only"
    SKIRT_ONLY = "skirt_only"
    BOTH = "both"
    INSUFFICIENT = "insufficient"


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
