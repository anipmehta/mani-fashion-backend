"""Unit tests for CLI --scan flag integration."""
from __future__ import annotations

import json
import pathlib

import pytest

from agentic_pattern_engine.cli import _parse_args, main

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures"


# ── Happy-path tests ────────────────────────────────────────────────────

def test_scanner_cli_3dlook_full_body_runs(tmp_path: pathlib.Path) -> None:
    fixture = FIXTURES / "3dlook_full_body.json"
    out = tmp_path / "out"
    result = main(["--scan", str(fixture), "--output-dir", str(out)])
    assert result == 0


def test_scanner_cli_generic_fixture_runs(tmp_path: pathlib.Path) -> None:
    fixture = FIXTURES / "generic_mani.json"
    out = tmp_path / "out"
    result = main(["--scan", str(fixture), "--output-dir", str(out)])
    assert result == 0


def test_scanner_cli_auto_selects_bodice_when_both(
    capsys: pytest.CaptureFixture[str],
    tmp_path: pathlib.Path,
) -> None:
    fixture = FIXTURES / "3dlook_full_body.json"
    out = tmp_path / "out"
    result = main(["--scan", str(fixture), "--output-dir", str(out)])
    assert result == 0
    captured = capsys.readouterr().out
    assert "Garment: bodice" in captured


def test_scanner_cli_garment_override_skirt(
    capsys: pytest.CaptureFixture[str],
    tmp_path: pathlib.Path,
) -> None:
    fixture = FIXTURES / "3dlook_full_body.json"
    out = tmp_path / "out"
    result = main([
        "--scan", str(fixture),
        "--garment", "skirt",
        "--output-dir", str(out),
    ])
    assert result == 0
    captured = capsys.readouterr().out
    assert "Garment: skirt" in captured


# ── Error-path tests ────────────────────────────────────────────────────

def test_scanner_cli_bodice_only_with_garment_skirt_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = FIXTURES / "3dlook_upper_only.json"
    with pytest.raises(SystemExit) as exc_info:
        main(["--scan", str(fixture), "--garment", "skirt"])
    assert exc_info.value.code == 1
    captured = capsys.readouterr().out
    assert "Error" in captured


def test_scanner_cli_nonexistent_file_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--scan", "/tmp/does_not_exist_12345.json"])
    assert exc_info.value.code == 1
    captured = capsys.readouterr().out
    assert "scan file not found" in captured


def test_scanner_cli_invalid_json_errors(
    capsys: pytest.CaptureFixture[str],
    tmp_path: pathlib.Path,
) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json!!!")
    with pytest.raises(SystemExit) as exc_info:
        main(["--scan", str(bad_file)])
    assert exc_info.value.code == 1
    captured = capsys.readouterr().out
    assert "invalid JSON" in captured


def test_scanner_cli_unrecognized_format_errors(
    capsys: pytest.CaptureFixture[str],
    tmp_path: pathlib.Path,
) -> None:
    unrecognized = tmp_path / "unknown.json"
    unrecognized.write_text(json.dumps({"foo": "bar", "baz": 42}))
    with pytest.raises(SystemExit) as exc_info:
        main(["--scan", str(unrecognized)])
    assert exc_info.value.code == 1
    captured = capsys.readouterr().out
    assert "Error" in captured


def test_scanner_cli_mutually_exclusive_with_chest() -> None:
    with pytest.raises(SystemExit) as exc_info:
        _parse_args(["--scan", "file.json", "--chest", "90.0"])
    assert exc_info.value.code == 2
