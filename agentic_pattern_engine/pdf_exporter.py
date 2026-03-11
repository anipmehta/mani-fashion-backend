"""PDF Exporter — export BodiceSloper to PDF using reportlab.

Generates a multi-page PDF with a cover page (measurement summary,
run summary, timestamp) followed by pattern piece pages at 1:1 scale
with tiling marks for A4/Letter printing.
"""

from __future__ import annotations

import io
import math
from datetime import datetime, timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from agentic_pattern_engine.models import (
    BodiceSloper,
    ExportMetadata,
    MeasurementProfile,
    PatternPiece,
    Point2D,
)

# A4 dimensions in points
_PAGE_W, _PAGE_H = A4
# Printable margin
_MARGIN = 1.5 * cm


class PDFPatternExporter:
    """Export BodiceSloper patterns to PDF at 1:1 scale."""

    def export(
        self,
        sloper: BodiceSloper,
        metadata: ExportMetadata,
        profile: MeasurementProfile,
    ) -> bytes:
        """Export sloper to PDF with cover page and pattern pages."""
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)

        # --- Cover page ---
        self._draw_cover(c, sloper, metadata, profile)
        c.showPage()

        # --- Pattern pages (1:1 scale) ---
        for piece in (sloper.front_bodice, sloper.back_bodice):
            self._draw_piece_page(c, piece)
            c.showPage()

        c.save()
        return buf.getvalue()

    def _draw_cover(
        self,
        c: canvas.Canvas,
        sloper: BodiceSloper,
        metadata: ExportMetadata,
        profile: MeasurementProfile,
    ) -> None:
        """Draw the cover page with measurement summary and run info."""
        y = _PAGE_H - _MARGIN - 40

        c.setFont("Helvetica-Bold", 20)
        c.drawString(_MARGIN, y, "MANI Pattern Export")
        y -= 30

        c.setFont("Helvetica", 12)
        c.drawString(_MARGIN, y, f"Generated: {datetime.now(timezone.utc).isoformat()}")
        y -= 20
        c.drawString(_MARGIN, y, f"Run ID: {metadata.run_id}")
        y -= 20
        c.drawString(_MARGIN, y, f"Status: {metadata.convergence_status}")
        y -= 20
        c.drawString(_MARGIN, y, f"Iterations: {metadata.iteration_count}")
        y -= 40

        c.setFont("Helvetica-Bold", 14)
        c.drawString(_MARGIN, y, "Measurement Summary")
        y -= 25

        c.setFont("Helvetica", 11)
        for label, val in [
            ("Chest", profile.chest),
            ("Waist", profile.waist),
            ("Hip", profile.hip),
            ("Shoulder Width", profile.shoulder_width),
            ("Torso Length", profile.torso_length),
        ]:
            c.drawString(_MARGIN + 10, y, f"{label}: {val:.1f} cm")
            y -= 18

        y -= 20
        c.setFont("Helvetica-Bold", 14)
        c.drawString(_MARGIN, y, "Sloper Parameters")
        y -= 25

        c.setFont("Helvetica", 11)
        c.drawString(_MARGIN + 10, y, f"Bust Ease: {sloper.bust_ease:.1f} cm")
        y -= 18
        c.drawString(_MARGIN + 10, y, f"Waist Ease: {sloper.waist_ease:.1f} cm")

    def _draw_piece_page(
        self,
        c: canvas.Canvas,
        piece: PatternPiece,
    ) -> None:
        """Draw a pattern piece at 1:1 scale with tiling marks."""
        c.setFont("Helvetica-Bold", 14)
        c.drawString(_MARGIN, _PAGE_H - _MARGIN - 20, piece.label)

        if not piece.outline:
            return

        # Convert cm to points (1 cm = 28.35 pt)
        scale = cm  # reportlab's cm unit

        # Compute bounding box
        xs = [p.x for p in piece.outline]
        ys = [p.y for p in piece.outline]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        # Offset to center on page
        piece_w = (x_max - x_min) * scale
        piece_h = (y_max - y_min) * scale
        avail_w = _PAGE_W - 2 * _MARGIN
        avail_h = _PAGE_H - 2 * _MARGIN - 40  # room for title

        # Scale down if piece is larger than page (tiling would be needed)
        fit_scale = min(avail_w / max(piece_w, 1), avail_h / max(piece_h, 1), 1.0)

        ox = _MARGIN + (avail_w - piece_w * fit_scale) / 2
        oy = _MARGIN + (avail_h - piece_h * fit_scale) / 2

        def tx(p: Point2D) -> tuple[float, float]:
            return (
                ox + (p.x - x_min) * scale * fit_scale,
                oy + (p.y - y_min) * scale * fit_scale,
            )

        # Draw outline
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(1)
        path = c.beginPath()
        sx, sy = tx(piece.outline[0])
        path.moveTo(sx, sy)
        for pt in piece.outline[1:]:
            px, py = tx(pt)
            path.lineTo(px, py)
        c.drawPath(path)

        # Draw darts
        c.setStrokeColorRGB(0.8, 0, 0)
        for dart in piece.darts:
            ax, ay = tx(dart.apex)
            half = dart.angle / 2.0
            r1 = math.radians(-half)
            r2 = math.radians(half)
            l = dart.length * scale * fit_scale
            c.line(ax, ay, ax + l * math.cos(r1), ay + l * math.sin(r1))
            c.line(ax, ay, ax + l * math.cos(r2), ay + l * math.sin(r2))

        # Draw grain line
        c.setStrokeColorRGB(0, 0, 0.8)
        c.setDash(6, 3)
        gsx, gsy = tx(piece.grain_line.start)
        gex, gey = tx(piece.grain_line.end)
        c.line(gsx, gsy, gex, gey)
        c.setDash()

        # Tiling marks at page edges
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.setLineWidth(0.5)
        for edge_x in (_MARGIN, _PAGE_W - _MARGIN):
            c.line(edge_x, _MARGIN, edge_x, _MARGIN + 10)
            c.line(edge_x, _PAGE_H - _MARGIN - 10, edge_x, _PAGE_H - _MARGIN)
        for edge_y in (_MARGIN, _PAGE_H - _MARGIN):
            c.line(_MARGIN, edge_y, _MARGIN + 10, edge_y)
            c.line(_PAGE_W - _MARGIN - 10, edge_y, _PAGE_W - _MARGIN, edge_y)
