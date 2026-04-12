"""Tests for CLI --grade mode and skirt CLI support."""

from __future__ import annotations

import pathlib
import tempfile

import pytest

from agentic_pattern_engine.cli import main
from agentic_pattern_engine.dxf_exporter import DXFPatternExporter
from agentic_pattern_engine.models import (
    ExportMetadata,
    MeasurementProfile,
)
from agentic_pattern_engine.sloper_generator import ParsonsSloperGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MEDIUM_PROFILE = MeasurementProfile(
    chest=91.5, waist=73.5, hip=98.0,
    shoulder_width=40.0, torso_length=42.5,
)


def _generate_dxf_file() -> str:
    """Generate a DXF file and return its path."""
    gen = ParsonsSloperGenerator()
    sloper = gen.generate(_MEDIUM_PROFILE)
    exporter = DXFPatternExporter()
    meta = ExportMetadata(
        profile_hash="test1234",
        run_id="run-001",
        iteration_count=3,
        convergence_status="converged",
    )
    dxf_bytes = exporter.export(sloper, meta)
    f = tempfile.NamedTemporaryFile(
        suffix=".dxf", delete=False, mode="wb",
    )
    f.write(dxf_bytes)
    f.close()
    return f.name


def _make_temp_file(suffix: str, content: str) -> str:
    """Write content to a temp file and return its path."""
    f = tempfile.NamedTemporaryFile(
        suffix=suffix, delete=False, mode="w",
    )
    f.write(content)
    f.close()
    return f.name


# ---------------------------------------------------------------------------
# CLI --grade tests
# ---------------------------------------------------------------------------


def test_cli_grade_valid_dxf_with_target_measurements(
    capsys, tmp_path,
):
    """--grade with valid DXF + target measurements should succeed."""
    dxf_path = _generate_dxf_file()
    out_dir = str(tmp_path / "graded_output")

    rc = main([
        "--grade", dxf_path,
        "--chest", "102.0",
        "--waist", "84.0",
        "--hip", "109.0",
        "--shoulder-width", "43.0",
        "--torso-length", "44.0",
        "--output-dir", out_dir,
    ])

    captured = capsys.readouterr()
    assert rc == 0
    assert "GRADING SUMMARY" in captured.out
    assert "Deltas" in captured.out
    assert "Self-correction" in captured.out

    pathlib.Path(dxf_path).unlink(missing_ok=True)


def test_cli_grade_without_target_measurements_errors(capsys):
    """--grade without target measurements should print error."""
    dxf_path = _generate_dxf_file()

    rc = main(["--grade", dxf_path])

    captured = capsys.readouterr()
    assert rc == 1
    assert "target measurements required" in captured.out.lower()

    pathlib.Path(dxf_path).unlink(missing_ok=True)


def test_cli_grade_unrecognized_format_errors(capsys):
    """--grade with .txt file should print supported formats error."""
    txt_path = _make_temp_file(".txt", "not a pattern")

    rc = main([
        "--grade", txt_path,
        "--chest", "91.5",
        "--waist", "73.5",
        "--hip", "98.0",
        "--shoulder-width", "40.0",
        "--torso-length", "42.5",
    ])

    captured = capsys.readouterr()
    assert rc == 1
    assert "Unrecognized format" in captured.out
    assert ".dxf" in captured.out
    assert ".svg" in captured.out

    pathlib.Path(txt_path).unlink(missing_ok=True)


def test_cli_grade_verbose_prints_audit_trail(capsys, tmp_path):
    """--grade --verbose should print per-iteration audit trail."""
    dxf_path = _generate_dxf_file()
    out_dir = str(tmp_path / "verbose_output")

    rc = main([
        "--grade", dxf_path,
        "--chest", "102.0",
        "--waist", "84.0",
        "--hip", "109.0",
        "--shoulder-width", "43.0",
        "--torso-length", "44.0",
        "--verbose",
        "--output-dir", out_dir,
    ])

    captured = capsys.readouterr()
    assert rc == 0
    assert "AUDIT TRAIL" in captured.out
    assert "Iteration" in captured.out

    pathlib.Path(dxf_path).unlink(missing_ok=True)


def test_cli_grade_summary_contains_required_fields(capsys, tmp_path):
    """Grading summary should contain deltas and convergence status."""
    dxf_path = _generate_dxf_file()
    out_dir = str(tmp_path / "summary_output")

    rc = main([
        "--grade", dxf_path,
        "--chest", "102.0",
        "--waist", "84.0",
        "--hip", "109.0",
        "--shoulder-width", "43.0",
        "--torso-length", "44.0",
        "--output-dir", out_dir,
    ])

    captured = capsys.readouterr()
    assert rc == 0
    # Should contain delta fields
    assert "chest:" in captured.out
    assert "waist:" in captured.out
    # Should contain convergence info
    assert "Self-correction:" in captured.out
    assert "Iterations:" in captured.out
    assert "Graded pieces:" in captured.out

    pathlib.Path(dxf_path).unlink(missing_ok=True)


def test_cli_grade_with_profile_json(capsys, tmp_path):
    """--grade with --profile JSON should work."""
    import json

    dxf_path = _generate_dxf_file()
    profile_data = {
        "chest": 102.0, "waist": 84.0, "hip": 109.0,
        "shoulder_width": 43.0, "torso_length": 44.0,
    }
    profile_path = str(tmp_path / "target.json")
    pathlib.Path(profile_path).write_text(json.dumps(profile_data))
    out_dir = str(tmp_path / "profile_output")

    rc = main([
        "--grade", dxf_path,
        "--profile", profile_path,
        "--output-dir", out_dir,
    ])

    captured = capsys.readouterr()
    assert rc == 0
    assert "GRADING SUMMARY" in captured.out

    pathlib.Path(dxf_path).unlink(missing_ok=True)


def test_cli_grade_exports_dxf(tmp_path):
    """--grade should export re-graded pattern as DXF."""
    dxf_path = _generate_dxf_file()
    out_dir = str(tmp_path / "export_output")

    rc = main([
        "--grade", dxf_path,
        "--chest", "102.0",
        "--waist", "84.0",
        "--hip", "109.0",
        "--shoulder-width", "43.0",
        "--torso-length", "44.0",
        "--output-dir", out_dir,
    ])

    assert rc == 0
    graded_dxf = tmp_path / "export_output" / "graded_pattern.dxf"
    assert graded_dxf.exists()
    assert graded_dxf.stat().st_size > 0

    pathlib.Path(dxf_path).unlink(missing_ok=True)
