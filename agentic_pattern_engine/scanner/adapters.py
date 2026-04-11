"""Scanner adapters: ThreeDLookAdapter and GenericAdapter."""
from __future__ import annotations

from agentic_pattern_engine.scanner.models import GarmentHint, ScanResult
from agentic_pattern_engine.units import convert_measurements

# ── Field sets used for garment-hint detection ──────────────────────────
BODICE_FIELDS: frozenset[str] = frozenset({
    "chest", "waist", "hip", "shoulder_width", "torso_length",
})
SKIRT_FIELDS: frozenset[str] = frozenset({
    "waist", "hip", "hip_depth", "desired_length",
})


def _detect_garment_hints(measurements: dict[str, float]) -> GarmentHint:
    """Determine which garment types *measurements* can support."""
    keys = set(measurements.keys())
    has_bodice = BODICE_FIELDS.issubset(keys)
    has_skirt = SKIRT_FIELDS.issubset(keys)
    if has_bodice and has_skirt:
        return GarmentHint.BOTH
    if has_bodice:
        return GarmentHint.BODICE_ONLY
    if has_skirt:
        return GarmentHint.SKIRT_ONLY
    return GarmentHint.INSUFFICIENT


# ── ThreeDLookAdapter ───────────────────────────────────────────────────

class ThreeDLookAdapter:
    """Adapter for 3DLOOK Mobile Tailor JSON output."""

    # MANI field → priority-ordered list of 3DLOOK aliases
    FIELD_MAP: dict[str, list[str]] = {
        "chest": ["bust_girth", "chest"],
        "waist": ["waist_girth", "natural_waist"],
        "hip": ["hip_girth", "hips"],
        "shoulder_width": ["across_shoulder", "shoulder_width"],
        "torso_length": ["back_length", "center_back_length"],
        "hip_depth": ["hip_depth", "waist_to_hip"],
        "desired_length": ["outseam", "side_seam_length"],
    }

    @property
    def scanner_name(self) -> str:
        return "3dlook"

    def can_handle(self, data: dict) -> bool:
        """Return True when the JSON looks like 3DLOOK output."""
        if "bust_girth" in data or "waist_girth" in data:
            return True
        source = data.get("source", "")
        if isinstance(source, str) and "3dlook" in source.lower():
            return True
        return False

    def parse(self, data: dict) -> ScanResult:
        """Map 3DLOOK fields to MANI fields and return a ScanResult."""
        source_unit = data.get("units", "cm")
        raw_measurements: dict[str, float] = {}

        for mani_field, aliases in self.FIELD_MAP.items():
            for alias in aliases:
                if alias in data and isinstance(data[alias], (int, float)):
                    raw_measurements[mani_field] = float(data[alias])
                    break  # first matching alias wins

        measurements = convert_measurements(raw_measurements, source_unit)
        # Normalise source_unit to canonical form
        canonical_unit = (
            "in" if source_unit.strip().lower() in {"in", "inches"} else "cm"
        )

        return ScanResult(
            measurements=measurements,
            source_unit=canonical_unit,
            scanner_type=self.scanner_name,
            garment_hints=_detect_garment_hints(measurements),
            raw_data=dict(data),
        )


# ── GenericAdapter ──────────────────────────────────────────────────────

class GenericAdapter:
    """Fallback adapter for JSON using MANI's own field names."""

    MANI_FIELDS: frozenset[str] = frozenset({
        "chest", "waist", "hip", "shoulder_width",
        "torso_length", "hip_depth", "desired_length",
    })

    @property
    def scanner_name(self) -> str:
        return "generic"

    def can_handle(self, data: dict) -> bool:
        """Return True when the dict has both waist and hip with numeric values."""
        return (
            isinstance(data.get("waist"), (int, float))
            and isinstance(data.get("hip"), (int, float))
        )

    def parse(self, data: dict) -> ScanResult:
        """Extract recognised MANI fields, ignore unknown keys."""
        source_unit = data.get("units", "cm")
        raw_measurements: dict[str, float] = {
            k: float(v)
            for k, v in data.items()
            if k in self.MANI_FIELDS and isinstance(v, (int, float))
        }

        measurements = convert_measurements(raw_measurements, source_unit)
        canonical_unit = (
            "in" if source_unit.strip().lower() in {"in", "inches"} else "cm"
        )

        return ScanResult(
            measurements=measurements,
            source_unit=canonical_unit,
            scanner_type=self.scanner_name,
            garment_hints=_detect_garment_hints(measurements),
            raw_data=dict(data),
        )
