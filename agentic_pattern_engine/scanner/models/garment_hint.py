"""GarmentHint enum — indicates which garment types a scan supports."""
from __future__ import annotations

from enum import Enum


class GarmentHint(Enum):
    """Indicates which garment types a scan's measurements can support."""

    BODICE_ONLY = "bodice_only"
    SKIRT_ONLY = "skirt_only"
    BOTH = "both"
    INSUFFICIENT = "insufficient"
