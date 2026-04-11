"""Scanner integration package — public API re-exports."""
from __future__ import annotations

from agentic_pattern_engine.scanner.adapters import (
    GenericAdapter,
    ThreeDLookAdapter,
)
from agentic_pattern_engine.scanner.models import GarmentHint, ScanResult
from agentic_pattern_engine.scanner.profile_converter import (
    scan_result_to_bodice_profile,
    scan_result_to_dict,
    scan_result_to_skirt_profile,
)
from agentic_pattern_engine.scanner.protocol import ScannerAdapter
from agentic_pattern_engine.scanner.registry import AdapterRegistry
from agentic_pattern_engine.units import (
    cm_to_inches,
    convert_measurements,
    inches_to_cm,
)

__all__ = [
    # Models
    "ScanResult",
    "GarmentHint",
    # Protocol
    "ScannerAdapter",
    # Adapters
    "ThreeDLookAdapter",
    "GenericAdapter",
    # Registry
    "AdapterRegistry",
    # Profile conversion
    "scan_result_to_bodice_profile",
    "scan_result_to_skirt_profile",
    "scan_result_to_dict",
    # Unit conversion (convenience re-exports)
    "inches_to_cm",
    "cm_to_inches",
    "convert_measurements",
]
