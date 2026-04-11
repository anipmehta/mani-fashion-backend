"""Profile conversion — bridge between ScanResult and engine profiles."""
from __future__ import annotations

from agentic_pattern_engine.models import (
    MeasurementProfile,
    SkirtMeasurementProfile,
)
from agentic_pattern_engine.scanner.models import GarmentHint, ScanResult

# Required fields for each garment type
BODICE_REQUIRED: frozenset[str] = frozenset({
    "chest", "waist", "hip", "shoulder_width", "torso_length",
})
SKIRT_REQUIRED: frozenset[str] = frozenset({
    "waist", "hip", "hip_depth", "desired_length",
})

# Garment hints that are incompatible with each conversion direction
_BODICE_INCOMPATIBLE: frozenset[GarmentHint] = frozenset({
    GarmentHint.SKIRT_ONLY,
    GarmentHint.INSUFFICIENT,
})
_SKIRT_INCOMPATIBLE: frozenset[GarmentHint] = frozenset({
    GarmentHint.BODICE_ONLY,
    GarmentHint.INSUFFICIENT,
})


def scan_result_to_bodice_profile(
    result: ScanResult,
) -> MeasurementProfile:
    """Convert a ScanResult to a MeasurementProfile for bodice generation.

    Raises ``ValueError`` when the scan's garment hints are incompatible
    with bodice generation, when required fields are missing, or when the
    resulting profile fails validation.
    """
    if result.garment_hints in _BODICE_INCOMPATIBLE:
        raise ValueError(
            f"Scan garment hints '{result.garment_hints.value}' "
            "are incompatible with bodice generation"
        )

    missing = BODICE_REQUIRED - result.measurements.keys()
    if missing:
        raise ValueError(
            f"Missing required bodice fields: {sorted(missing)}"
        )

    profile = MeasurementProfile(
        chest=result.measurements["chest"],
        waist=result.measurements["waist"],
        hip=result.measurements["hip"],
        shoulder_width=result.measurements["shoulder_width"],
        torso_length=result.measurements["torso_length"],
    )

    errors = profile.validate()
    if errors:
        raise ValueError(
            f"Bodice profile validation failed: {'; '.join(errors)}"
        )
    return profile


def scan_result_to_skirt_profile(
    result: ScanResult,
) -> SkirtMeasurementProfile:
    """Convert a ScanResult to a SkirtMeasurementProfile.

    Raises ``ValueError`` when the scan's garment hints are incompatible
    with skirt generation, when required fields are missing, or when the
    resulting profile fails validation.
    """
    if result.garment_hints in _SKIRT_INCOMPATIBLE:
        raise ValueError(
            f"Scan garment hints '{result.garment_hints.value}' "
            "are incompatible with skirt generation"
        )

    missing = SKIRT_REQUIRED - result.measurements.keys()
    if missing:
        raise ValueError(
            f"Missing required skirt fields: {sorted(missing)}"
        )

    profile = SkirtMeasurementProfile(
        waist=result.measurements["waist"],
        hip=result.measurements["hip"],
        hip_depth=result.measurements["hip_depth"],
        desired_length=result.measurements["desired_length"],
    )

    errors = profile.validate()
    if errors:
        raise ValueError(
            f"Skirt profile validation failed: {'; '.join(errors)}"
        )
    return profile


def scan_result_to_dict(result: ScanResult) -> dict:
    """Serialize a ScanResult to a JSON-compatible dictionary.

    Keys: measurements, source_unit, scanner_type, garment_hints (string
    value), raw_data, confidence_scores.
    """
    return {
        "measurements": dict(result.measurements),
        "source_unit": result.source_unit,
        "scanner_type": result.scanner_type,
        "garment_hints": result.garment_hints.value,
        "raw_data": dict(result.raw_data),
        "confidence_scores": (
            dict(result.confidence_scores)
            if result.confidence_scores is not None
            else None
        ),
    }
