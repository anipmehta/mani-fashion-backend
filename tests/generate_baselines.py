"""Generate bodice regression baseline JSON snapshots.

Runs the existing bodice pipeline for 3 profiles (standard, plus, petite)
and serializes the AgentRunResult to deterministic JSON files in
tests/baselines/.

Usage:
    python -m tests.generate_baselines
"""

from __future__ import annotations

import dataclasses
import json
import math
import pathlib
from typing import Any

from agentic_pattern_engine.agent_orchestrator import AgentOrchestrator
from agentic_pattern_engine.models import (
    AgentRunResult,
    BodiceSloper,
    DartGeometry,
    Line2D,
    MeasurementProfile,
    PatternPiece,
    Point2D,
)

# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

PROFILES: dict[str, MeasurementProfile] = {
    "standard": MeasurementProfile(
        chest=88.0, waist=70.0, hip=96.0,
        shoulder_width=40.0, torso_length=42.0,
    ),
    "plus": MeasurementProfile(
        chest=120.0, waist=105.0, hip=125.0,
        shoulder_width=46.0, torso_length=45.0,
    ),
    "petite": MeasurementProfile(
        chest=78.0, waist=62.0, hip=86.0,
        shoulder_width=36.0, torso_length=38.0,
    ),
}

BASELINES_DIR = pathlib.Path(__file__).parent / "baselines"
FLOAT_PRECISION = 6


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _round_float(value: float, precision: int = FLOAT_PRECISION) -> float:
    """Round a float to fixed precision for deterministic output."""
    if math.isnan(value) or math.isinf(value):
        return value
    return round(value, precision)


def _point_to_dict(p: Point2D) -> dict[str, float]:
    return {"x": _round_float(p.x), "y": _round_float(p.y)}


def _line_to_dict(ln: Line2D) -> dict[str, Any]:
    return {
        "start": _point_to_dict(ln.start),
        "end": _point_to_dict(ln.end),
    }


def _dart_to_dict(d: DartGeometry) -> dict[str, Any]:
    return {
        "apex": _point_to_dict(d.apex),
        "angle": _round_float(d.angle),
        "length": _round_float(d.length),
    }


def _piece_to_dict(piece: PatternPiece) -> dict[str, Any]:
    return {
        "piece_id": piece.piece_id,
        "label": piece.label,
        "outline": [_point_to_dict(p) for p in piece.outline],
        "seam_lines": [_line_to_dict(ln) for ln in piece.seam_lines],
        "darts": [_dart_to_dict(d) for d in piece.darts],
        "grain_line": _line_to_dict(piece.grain_line),
        "notch_marks": [_point_to_dict(p) for p in piece.notch_marks],
        "seam_allowance": _round_float(piece.seam_allowance),
    }


def _sloper_to_dict(sloper: BodiceSloper) -> dict[str, Any]:
    return {
        "sloper_id": sloper.sloper_id,
        "front_bodice": _piece_to_dict(sloper.front_bodice),
        "back_bodice": _piece_to_dict(sloper.back_bodice),
        "bust_ease": _round_float(sloper.bust_ease),
        "waist_ease": _round_float(sloper.waist_ease),
    }


def _profile_to_dict(profile: MeasurementProfile) -> dict[str, float]:
    return {
        "chest": profile.chest,
        "waist": profile.waist,
        "hip": profile.hip,
        "shoulder_width": profile.shoulder_width,
        "torso_length": profile.torso_length,
    }


def serialize_result(
    result: AgentRunResult,
    profile: MeasurementProfile,
) -> dict[str, Any]:
    """Serialize an AgentRunResult to a deterministic dict."""
    data: dict[str, Any] = {
        "profile": _profile_to_dict(profile),
        "convergence_status": result.convergence_status.value,
        "total_iterations": result.total_iterations,
    }

    if result.final_sloper is not None:
        data["final_sloper"] = _sloper_to_dict(result.final_sloper)

    return data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate_baselines() -> None:
    """Run the pipeline for each profile and write baseline JSON files."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)

    orchestrator = AgentOrchestrator()

    for name, profile in PROFILES.items():
        print(f"Generating baseline for '{name}' profile...")
        result = orchestrator.run(profile)

        data = serialize_result(result, profile)
        out_path = BASELINES_DIR / f"bodice_{name}.json"
        out_path.write_text(
            json.dumps(data, sort_keys=True, indent=2) + "\n"
        )
        print(
            f"  -> {out_path}  "
            f"(status={result.convergence_status.value}, "
            f"iterations={result.total_iterations})"
        )

    print("Done.")


if __name__ == "__main__":
    generate_baselines()
