"""Bodice regression and snapshot tests.

Validates that the existing bodice pipeline produces identical output
for known measurement profiles, guarding against regressions during
refactoring.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from agentic_pattern_engine.agent_orchestrator import AgentOrchestrator
from agentic_pattern_engine.models import MeasurementProfile

from tests.generate_baselines import (
    PROFILES,
    serialize_result,
)

BASELINES_DIR = pathlib.Path(__file__).parent / "baselines"

TOLERANCE = 0.001  # cm / degrees


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_baseline(name: str) -> dict[str, Any]:
    """Load a baseline JSON file by profile name."""
    path = BASELINES_DIR / f"bodice_{name}.json"
    return json.loads(path.read_text())


def _collect_numeric_fields(
    data: dict[str, Any],
    prefix: str = "",
) -> dict[str, float]:
    """Recursively collect all numeric leaf values with dotted key paths."""
    result: dict[str, float] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, (int, float)):
            result[full_key] = float(value)
        elif isinstance(value, dict):
            result.update(_collect_numeric_fields(value, full_key))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    result.update(
                        _collect_numeric_fields(item, f"{full_key}[{i}]")
                    )
                elif isinstance(item, (int, float)):
                    result[f"{full_key}[{i}]"] = float(item)
    return result


def _run_pipeline(profile: MeasurementProfile) -> dict[str, Any]:
    """Run the bodice pipeline and return serialized result."""
    orchestrator = AgentOrchestrator()
    result = orchestrator.run(profile)
    return serialize_result(result, profile)


# ---------------------------------------------------------------------------
# Snapshot tests — full JSON structure comparison (excluding sloper_id)
# Requirements: 1.1, 1.2
# ---------------------------------------------------------------------------


def _strip_sloper_id(data: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy with sloper_id removed (UUID is non-deterministic)."""
    data = json.loads(json.dumps(data))  # deep copy
    if "final_sloper" in data and "sloper_id" in data["final_sloper"]:
        del data["final_sloper"]["sloper_id"]
    return data


@pytest.mark.parametrize("profile_name", ["standard", "plus", "petite"])
def test_bodice_regression_snapshot(profile_name: str) -> None:
    """Serialize BodiceSloper to JSON and compare against stored baseline.

    Requirements: 1.1, 1.2
    """
    baseline = _strip_sloper_id(_load_baseline(profile_name))
    actual = _strip_sloper_id(_run_pipeline(PROFILES[profile_name]))
    assert actual == baseline, (
        f"Snapshot mismatch for '{profile_name}' profile. "
        f"Re-run `python -m tests.generate_baselines` if the change is intentional."
    )


# ---------------------------------------------------------------------------
# Regression tests — numeric field tolerance checks
# Requirements: 1.1, 1.3
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("profile_name", ["standard", "plus", "petite"])
def test_bodice_regression_numeric_tolerance(profile_name: str) -> None:
    """Assert every numeric output field matches within 0.001 tolerance.

    When a field deviates, the error message identifies the field and
    the magnitude of deviation.

    Requirements: 1.1, 1.3
    """
    baseline = _load_baseline(profile_name)
    actual = _run_pipeline(PROFILES[profile_name])

    baseline_nums = _collect_numeric_fields(baseline)
    actual_nums = _collect_numeric_fields(actual)

    # Check all baseline fields are present in actual
    missing = set(baseline_nums) - set(actual_nums)
    assert not missing, f"Missing fields in actual output: {missing}"

    deviations: list[str] = []
    for field_path, expected_val in baseline_nums.items():
        actual_val = actual_nums[field_path]
        diff = abs(actual_val - expected_val)
        if diff > TOLERANCE:
            deviations.append(
                f"  {field_path}: expected={expected_val}, "
                f"actual={actual_val}, diff={diff:.6f}"
            )

    assert not deviations, (
        f"Numeric regression for '{profile_name}' profile — "
        f"fields exceeding {TOLERANCE} tolerance:\n"
        + "\n".join(deviations)
    )


# ---------------------------------------------------------------------------
# End-to-end test — full Orchestrator loop
# Requirements: 1.5
# ---------------------------------------------------------------------------

def test_bodice_regression_end_to_end_standard() -> None:
    """Run full Orchestrator self-correction loop for the standard profile.

    Assert convergence_status and total_iterations match the stored baseline.

    Requirements: 1.5
    """
    baseline = _load_baseline("standard")
    profile = PROFILES["standard"]

    orchestrator = AgentOrchestrator()
    result = orchestrator.run(profile)

    assert result.convergence_status.value == baseline["convergence_status"], (
        f"Convergence status mismatch: "
        f"expected={baseline['convergence_status']}, "
        f"actual={result.convergence_status.value}"
    )
    assert result.total_iterations == baseline["total_iterations"], (
        f"Iteration count mismatch: "
        f"expected={baseline['total_iterations']}, "
        f"actual={result.total_iterations}"
    )
