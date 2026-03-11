"""Property tests for the DXF Exporter.

Properties 20 and 21 from the design document.
"""

from __future__ import annotations

import io

import ezdxf
from hypothesis import given, settings

from agentic_pattern_engine.dxf_exporter import DXFPatternExporter
from agentic_pattern_engine.models import ExportMetadata
from tests.conftest import bodice_slopers

_exporter = DXFPatternExporter()

_META = ExportMetadata(
    profile_hash="testhash",
    run_id="test-run-001",
    iteration_count=5,
    convergence_status="converged",
)


# Feature: agentic-pattern-engine, Property 20: DXF export round-trip
@given(sloper=bodice_slopers())
@settings(max_examples=50)
def test_dxf_round_trip(sloper):
    """For any valid BodiceSloper, export to DXF then parse back
    should produce equivalent geometry within 0.1mm tolerance."""
    dxf_bytes = _exporter.export(sloper, _META)
    parsed = _exporter.parse(dxf_bytes)

    for orig_piece, parsed_piece in [
        (sloper.front_bodice, parsed.front_bodice),
        (sloper.back_bodice, parsed.back_bodice),
    ]:
        # Compare outlines within 0.01cm (0.1mm)
        assert len(parsed_piece.outline) > 0
        # The parsed outline may have closing point added; compare min length
        min_len = min(len(orig_piece.outline), len(parsed_piece.outline))
        for i in range(min_len):
            assert abs(orig_piece.outline[i].x - parsed_piece.outline[i].x) < 0.01, (
                f"Outline x mismatch at {i}: {orig_piece.outline[i].x} vs {parsed_piece.outline[i].x}"
            )
            assert abs(orig_piece.outline[i].y - parsed_piece.outline[i].y) < 0.01, (
                f"Outline y mismatch at {i}: {orig_piece.outline[i].y} vs {parsed_piece.outline[i].y}"
            )

        # Compare dart geometry
        assert len(parsed_piece.darts) == len(orig_piece.darts)
        for od, pd in zip(orig_piece.darts, parsed_piece.darts):
            assert abs(od.angle - pd.angle) < 0.01
            assert abs(od.length - pd.length) < 0.01

    # Compare sloper-level data
    assert abs(parsed.bust_ease - sloper.bust_ease) < 0.01
    assert abs(parsed.waist_ease - sloper.waist_ease) < 0.01


# Feature: agentic-pattern-engine, Property 21: DXF export completeness
@given(sloper=bodice_slopers())
@settings(max_examples=50)
def test_dxf_export_completeness(sloper):
    """For any valid BodiceSloper and ExportMetadata, the DXF must contain:
    - separate named layers for each piece
    - closed polyline outlines, seam lines, dart lines, grain lines,
      notch marks, seam allowance markings, and piece labels
    - metadata in custom properties
    """
    dxf_bytes = _exporter.export(sloper, _META)
    doc = ezdxf.read(io.StringIO(dxf_bytes.decode("utf-8")))
    msp = doc.modelspace()

    # Check layers exist
    layer_names = {layer.dxf.name for layer in doc.layers}
    assert "front_bodice" in layer_names
    assert "back_bodice" in layer_names

    # Check metadata in custom vars
    custom_vars = {tag_name: value for tag_name, value in doc.header.custom_vars}
    assert custom_vars.get("MANI_PROFILE_HASH") == _META.profile_hash
    assert custom_vars.get("MANI_RUN_ID") == _META.run_id
    assert custom_vars.get("MANI_STATUS") == _META.convergence_status

    # Check each layer has required elements
    for layer_name in ("front_bodice", "back_bodice"):
        entities = [e for e in msp if e.dxf.layer == layer_name]
        types = {e.dxftype() for e in entities}

        # Must have polyline (outline), lines (seam/dart/grain), text (labels), points (notches)
        assert "LWPOLYLINE" in types, f"{layer_name} missing outline polyline"
        assert "LINE" in types, f"{layer_name} missing lines"
        assert "TEXT" in types, f"{layer_name} missing text labels"
        assert "POINT" in types, f"{layer_name} missing notch points"

        # Check for dart text, seam allowance text, and label text
        texts = [e.dxf.text for e in entities if e.dxftype() == "TEXT"]
        has_dart = any(t.startswith("DT:") for t in texts)
        has_sa = any(t.startswith("SA:") for t in texts)
        has_label = any(t.startswith("LB:") for t in texts)
        assert has_dart, f"{layer_name} missing dart annotation"
        assert has_sa, f"{layer_name} missing seam allowance annotation"
        assert has_label, f"{layer_name} missing piece label"
