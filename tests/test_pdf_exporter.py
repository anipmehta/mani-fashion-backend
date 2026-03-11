"""Tests for the PDF Exporter and Property 22 (export availability)."""

from __future__ import annotations

from agentic_pattern_engine.pdf_exporter import PDFPatternExporter
from agentic_pattern_engine.dxf_exporter import DXFPatternExporter
from agentic_pattern_engine.sloper_generator import ParsonsSloperGenerator
from agentic_pattern_engine.models import ExportMetadata
from tests.conftest import SAMPLE_PROFILES

_pdf_exporter = PDFPatternExporter()
_dxf_exporter = DXFPatternExporter()
_generator = ParsonsSloperGenerator()

_META = ExportMetadata(
    profile_hash="testhash",
    run_id="test-run-001",
    iteration_count=5,
    convergence_status="converged",
)


def test_pdf_export_produces_bytes():
    """PDF export must produce non-empty bytes for any valid sloper."""
    for name, profile in SAMPLE_PROFILES.items():
        sloper = _generator.generate(profile)
        pdf_bytes = _pdf_exporter.export(sloper, _META, profile)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0, f"Empty PDF for profile {name}"
        # PDF magic bytes
        assert pdf_bytes[:5] == b"%PDF-"


def test_pdf_cover_page_content():
    """PDF must be a valid multi-page PDF (cover + 2 piece pages)."""
    profile = SAMPLE_PROFILES["medium"]
    sloper = _generator.generate(profile)
    pdf_bytes = _pdf_exporter.export(sloper, _META, profile)
    # PDF should have 3 pages (cover + front + back)
    # Count /Type /Page occurrences in raw bytes
    page_count = pdf_bytes.count(b"/Type /Page\n")
    assert page_count >= 3, f"Expected at least 3 pages, found {page_count}"


# Feature: agentic-pattern-engine, Property 22: Export availability
def test_export_availability():
    """For any completed run with non-null final_sloper, both DXF and PDF
    must produce non-null bytes."""
    for name, profile in SAMPLE_PROFILES.items():
        sloper = _generator.generate(profile)
        dxf_bytes = _dxf_exporter.export(sloper, _META)
        pdf_bytes = _pdf_exporter.export(sloper, _META, profile)
        assert dxf_bytes is not None and len(dxf_bytes) > 0, f"No DXF for {name}"
        assert pdf_bytes is not None and len(pdf_bytes) > 0, f"No PDF for {name}"
