"""Tests for PatternParser — DXF/SVG parsing and garment type detection."""

from __future__ import annotations

import pathlib
import tempfile

import pytest

from agentic_pattern_engine.dxf_exporter import DXFPatternExporter
from agentic_pattern_engine.models import (
    DartGeometry,
    ExportMetadata,
    Line2D,
    MeasurementProfile,
    PatternPiece,
    Point2D,
)
from agentic_pattern_engine.pattern_parser import PatternParser
from agentic_pattern_engine.sloper_generator import ParsonsSloperGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MEDIUM_PROFILE = MeasurementProfile(
    chest=91.5, waist=73.5, hip=98.0,
    shoulder_width=40.0, torso_length=42.5,
)


def _generate_dxf_bytes() -> bytes:
    """Generate a DXF file from a bodice sloper for round-trip testing."""
    gen = ParsonsSloperGenerator()
    sloper = gen.generate(_MEDIUM_PROFILE)
    exporter = DXFPatternExporter()
    meta = ExportMetadata(
        profile_hash="test1234",
        run_id="run-001",
        iteration_count=3,
        convergence_status="converged",
    )
    return exporter.export(sloper, meta)


def _write_temp_file(suffix: str, content: bytes | str) -> str:
    """Write content to a temp file and return its path."""
    mode = "wb" if isinstance(content, bytes) else "w"
    f = tempfile.NamedTemporaryFile(
        suffix=suffix, delete=False, mode=mode,
    )
    f.write(content)
    f.close()
    return f.name


# ---------------------------------------------------------------------------
# DXF round-trip tests
# ---------------------------------------------------------------------------


def test_pattern_parser_dxf_round_trip_pieces_match():
    """Generate bodice → export DXF → parse back → verify pieces."""
    gen = ParsonsSloperGenerator()
    sloper = gen.generate(_MEDIUM_PROFILE)
    exporter = DXFPatternExporter()
    meta = ExportMetadata(
        profile_hash="abc", run_id="r1",
        iteration_count=1, convergence_status="converged",
    )
    dxf_bytes = exporter.export(sloper, meta)
    path = _write_temp_file(".dxf", dxf_bytes)

    parser = PatternParser()
    result = parser.parse(path)

    assert not result.errors, f"Unexpected errors: {result.errors}"
    assert len(result.pieces) == 2
    assert result.source_format == "dxf"

    # Verify front piece outline has same number of points
    orig_front = sloper.front_bodice
    parsed_front = result.pieces[0]
    assert len(parsed_front.outline) >= 3
    assert parsed_front.outline[0] == parsed_front.outline[-1]

    # Verify darts preserved
    assert len(parsed_front.darts) == len(orig_front.darts)
    for orig_d, parsed_d in zip(orig_front.darts, parsed_front.darts):
        assert abs(orig_d.angle - parsed_d.angle) < 0.01
        assert abs(orig_d.length - parsed_d.length) < 0.01

    pathlib.Path(path).unlink(missing_ok=True)


def test_pattern_parser_dxf_detects_bodice_garment_type():
    """DXF with bodice labels should detect garment type as 'bodice'."""
    dxf_bytes = _generate_dxf_bytes()
    path = _write_temp_file(".dxf", dxf_bytes)

    parser = PatternParser()
    result = parser.parse(path)

    assert result.garment_type == "bodice"
    pathlib.Path(path).unlink(missing_ok=True)


def test_pattern_parser_dxf_seam_allowance_preserved():
    """Seam allowance should survive DXF round-trip."""
    dxf_bytes = _generate_dxf_bytes()
    path = _write_temp_file(".dxf", dxf_bytes)

    parser = PatternParser()
    result = parser.parse(path)

    for piece in result.pieces:
        assert piece.seam_allowance > 0
    pathlib.Path(path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# SVG parsing tests
# ---------------------------------------------------------------------------

_SIMPLE_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="300">
  <polygon
    data-piece-id="front_bodice"
    data-label="Front Bodice"
    data-seam-allowance="1.5"
    data-darts="10,0,12.5,8.0"
    data-notches="5,0;12,20"
    data-grain-line="10,2,10,28"
    points="0,0 20,0 20,30 0,30" />
  <path
    data-piece-id="back_bodice"
    data-label="Back Bodice"
    data-seam-allowance="1.5"
    data-darts="8,0,11.0,7.5"
    data-notches="4,0;10,18"
    d="M 0 0 L 18 0 L 18 28 L 0 28 Z" />
</svg>
"""


def test_pattern_parser_svg_extracts_pieces():
    """SVG with data attributes should produce PatternPieces."""
    path = _write_temp_file(".svg", _SIMPLE_SVG)

    parser = PatternParser()
    result = parser.parse(path)

    assert not result.errors
    assert len(result.pieces) == 2
    assert result.source_format == "svg"

    front = result.pieces[0]
    assert front.piece_id == "front_bodice"
    assert front.label == "Front Bodice"
    assert front.seam_allowance == 1.5
    assert len(front.darts) == 1
    assert abs(front.darts[0].angle - 12.5) < 0.01
    assert len(front.notch_marks) == 2
    # Outline should be closed polygon
    assert front.outline[0] == front.outline[-1]

    pathlib.Path(path).unlink(missing_ok=True)


def test_pattern_parser_svg_detects_bodice_type():
    """SVG with bodice piece labels should detect garment type."""
    path = _write_temp_file(".svg", _SIMPLE_SVG)

    parser = PatternParser()
    result = parser.parse(path)

    assert result.garment_type == "bodice"
    pathlib.Path(path).unlink(missing_ok=True)


def test_pattern_parser_svg_path_element():
    """SVG path elements with M/L/Z commands should be parsed."""
    path = _write_temp_file(".svg", _SIMPLE_SVG)

    parser = PatternParser()
    result = parser.parse(path)

    back = result.pieces[1]
    assert back.piece_id == "back_bodice"
    assert len(back.outline) >= 4  # 4 corners + close
    assert back.outline[0] == back.outline[-1]

    pathlib.Path(path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Malformed / error tests
# ---------------------------------------------------------------------------


def test_pattern_parser_malformed_dxf_returns_errors():
    """Malformed DXF content should return descriptive errors."""
    path = _write_temp_file(".dxf", b"NOT A VALID DXF FILE")

    parser = PatternParser()
    result = parser.parse(path)

    assert len(result.errors) > 0
    assert "Malformed DXF" in result.errors[0]
    assert len(result.pieces) == 0

    pathlib.Path(path).unlink(missing_ok=True)


def test_pattern_parser_malformed_svg_returns_errors():
    """Malformed SVG content should return descriptive errors."""
    path = _write_temp_file(".svg", "<not-valid-xml><<<")

    parser = PatternParser()
    result = parser.parse(path)

    assert len(result.errors) > 0
    assert "Malformed SVG" in result.errors[0]

    pathlib.Path(path).unlink(missing_ok=True)


def test_pattern_parser_empty_svg_returns_errors():
    """SVG with no pattern pieces should return errors."""
    svg = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    path = _write_temp_file(".svg", svg)

    parser = PatternParser()
    result = parser.parse(path)

    assert len(result.errors) > 0
    assert "No pattern pieces" in result.errors[0]

    pathlib.Path(path).unlink(missing_ok=True)


def test_pattern_parser_unrecognized_format_returns_error():
    """Unrecognized file extension should return format error."""
    path = _write_temp_file(".txt", "some text content")

    parser = PatternParser()
    result = parser.parse(path)

    assert len(result.errors) > 0
    assert "Unrecognized format" in result.errors[0]
    assert ".dxf" in result.errors[0]
    assert ".svg" in result.errors[0]

    pathlib.Path(path).unlink(missing_ok=True)


def test_pattern_parser_file_not_found():
    """Non-existent file should return error."""
    parser = PatternParser()
    result = parser.parse("/nonexistent/path/file.dxf")

    assert len(result.errors) > 0
    assert "not found" in result.errors[0].lower() or "Cannot" in result.errors[0]


# ---------------------------------------------------------------------------
# Garment type detection tests
# ---------------------------------------------------------------------------


def test_pattern_parser_detect_garment_type_bodice():
    """Pieces with bodice labels should detect as 'bodice'."""
    parser = PatternParser()
    pieces = [
        PatternPiece(
            piece_id="front_bodice", label="Front Bodice",
            outline=(Point2D(0, 0), Point2D(1, 0), Point2D(0, 0)),
            seam_lines=(), darts=(),
            grain_line=Line2D(Point2D(0, 0), Point2D(0, 1)),
            notch_marks=(), seam_allowance=1.5,
        ),
    ]
    assert parser._detect_garment_type(pieces) == "bodice"


def test_pattern_parser_detect_garment_type_skirt():
    """Pieces with skirt labels should detect as 'skirt'."""
    parser = PatternParser()
    pieces = [
        PatternPiece(
            piece_id="front_skirt", label="Front Skirt",
            outline=(Point2D(0, 0), Point2D(1, 0), Point2D(0, 0)),
            seam_lines=(), darts=(),
            grain_line=Line2D(Point2D(0, 0), Point2D(0, 1)),
            notch_marks=(), seam_allowance=1.5,
        ),
    ]
    assert parser._detect_garment_type(pieces) == "skirt"


def test_pattern_parser_detect_garment_type_unknown():
    """Pieces with unrecognized labels should return None."""
    parser = PatternParser()
    pieces = [
        PatternPiece(
            piece_id="panel_a", label="Panel A",
            outline=(Point2D(0, 0), Point2D(1, 0), Point2D(0, 0)),
            seam_lines=(), darts=(),
            grain_line=Line2D(Point2D(0, 0), Point2D(0, 1)),
            notch_marks=(), seam_allowance=1.5,
        ),
    ]
    assert parser._detect_garment_type(pieces) is None
