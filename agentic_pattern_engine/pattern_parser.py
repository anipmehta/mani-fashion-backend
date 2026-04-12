"""Pattern Parser — parse DXF and SVG pattern files into PatternPiece lists.

Supports:
- DXF files produced by the existing DXFPatternExporter (round-trip)
- SVG files with pattern metadata in data attributes

Auto-detects format by file extension and garment type from piece labels.
"""

from __future__ import annotations

import pathlib
import re
import xml.etree.ElementTree as ET
from typing import Any

from agentic_pattern_engine.models import (
    DartGeometry,
    Line2D,
    ParseResult,
    PatternPiece,
    Point2D,
)

# Supported file extensions
SUPPORTED_FORMATS: frozenset[str] = frozenset({".dxf", ".svg"})

# Garment type detection keywords
_BODICE_LABELS: frozenset[str] = frozenset({
    "bodice", "front_bodice", "back_bodice",
    "front bodice", "back bodice",
})
_SKIRT_LABELS: frozenset[str] = frozenset({
    "front_skirt", "back_skirt",
    "front skirt", "back skirt",
})

# SVG namespace
_SVG_NS = "http://www.w3.org/2000/svg"

# Default seam allowance when not specified
_DEFAULT_SEAM_ALLOWANCE = 1.5


class PatternParser:
    """Parse DXF and SVG pattern files into PatternPiece lists."""

    def parse(self, file_path: str) -> ParseResult:
        """Auto-detect format by extension, delegate to parse_dxf or parse_svg."""
        path = pathlib.Path(file_path)
        ext = path.suffix.lower()

        if ext not in SUPPORTED_FORMATS:
            return ParseResult(
                pieces=[],
                garment_type=None,
                source_format=ext.lstrip(".") if ext else "unknown",
                warnings=[],
                errors=[
                    f"Unrecognized format '{ext}'. "
                    f"Supported formats: {', '.join(sorted(SUPPORTED_FORMATS))}"
                ],
            )

        if not path.exists():
            return ParseResult(
                pieces=[],
                garment_type=None,
                source_format=ext.lstrip("."),
                warnings=[],
                errors=[f"File not found: {file_path}"],
            )

        try:
            raw = path.read_bytes()
        except OSError as exc:
            return ParseResult(
                pieces=[],
                garment_type=None,
                source_format=ext.lstrip("."),
                warnings=[],
                errors=[f"Cannot read file: {exc}"],
            )

        if ext == ".dxf":
            return self.parse_dxf(file_path)
        return self.parse_svg(file_path)

    def parse_dxf(self, file_path: str) -> ParseResult:
        """Parse a DXF file into pattern pieces.

        Leverages the existing DXFPatternExporter.parse() method which
        reads DXF files produced by the engine. Extracts pattern pieces
        with outlines, seam lines, darts, grain lines, notch marks,
        and seam allowance.
        """
        from agentic_pattern_engine.dxf_exporter import DXFPatternExporter

        warnings: list[str] = []
        errors: list[str] = []

        path = pathlib.Path(file_path)
        try:
            dxf_bytes = path.read_bytes()
        except OSError as exc:
            return ParseResult(
                pieces=[], garment_type=None,
                source_format="dxf", warnings=[], errors=[str(exc)],
            )

        try:
            exporter = DXFPatternExporter()
            sloper = exporter.parse(dxf_bytes)
        except Exception as exc:
            return ParseResult(
                pieces=[], garment_type=None,
                source_format="dxf", warnings=[],
                errors=[f"Malformed DXF: {exc}"],
            )

        pieces = [sloper.front_bodice, sloper.back_bodice]

        # Validate extracted pieces
        for piece in pieces:
            if len(piece.outline) < 3:
                warnings.append(
                    f"Piece '{piece.label}' has fewer than 3 "
                    f"outline points"
                )

        garment_type = self._detect_garment_type(pieces)
        return ParseResult(
            pieces=pieces,
            garment_type=garment_type,
            source_format="dxf",
            warnings=warnings,
            errors=errors,
        )

    def parse_svg(self, file_path: str) -> ParseResult:
        """Parse an SVG file into pattern pieces.

        Extracts path elements as outlines. Supports pattern metadata
        in data attributes (data-piece-id, data-label, data-seam-allowance,
        data-dart-*, data-grain-*, data-notch-*).
        """
        warnings: list[str] = []
        errors: list[str] = []

        path = pathlib.Path(file_path)
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            return ParseResult(
                pieces=[], garment_type=None,
                source_format="svg", warnings=[], errors=[str(exc)],
            )

        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            return ParseResult(
                pieces=[], garment_type=None,
                source_format="svg", warnings=[],
                errors=[f"Malformed SVG: {exc}"],
            )

        pieces: list[PatternPiece] = []
        # Find all path or polygon elements with pattern metadata
        for elem in _iter_svg_elements(root):
            piece = self._svg_element_to_piece(elem, warnings)
            if piece is not None:
                pieces.append(piece)

        if not pieces:
            errors.append(
                "No pattern pieces found in SVG. Expected <path> or "
                "<polygon> elements with data-piece-id attributes."
            )

        garment_type = self._detect_garment_type(pieces)
        return ParseResult(
            pieces=pieces,
            garment_type=garment_type,
            source_format="svg",
            warnings=warnings,
            errors=errors,
        )

    def _detect_garment_type(
        self, pieces: list[PatternPiece],
    ) -> str | None:
        """Detect garment type from piece labels.

        Returns "bodice" if any label matches bodice keywords,
        "skirt" if any label matches skirt keywords, else None.
        """
        for piece in pieces:
            label_lower = piece.label.lower()
            piece_id_lower = piece.piece_id.lower()
            combined = {label_lower, piece_id_lower}
            for token in combined:
                if token in _BODICE_LABELS:
                    return "bodice"
                if token in _SKIRT_LABELS:
                    return "skirt"
            # Also check partial matches
            for token in combined:
                if "bodice" in token:
                    return "bodice"
                if "skirt" in token:
                    return "skirt"
        return None

    def _svg_element_to_piece(
        self,
        elem: ET.Element,
        warnings: list[str],
    ) -> PatternPiece | None:
        """Convert an SVG element to a PatternPiece."""
        piece_id = elem.get("data-piece-id", "")
        label = elem.get("data-label", piece_id)
        if not piece_id:
            return None

        # Parse outline from path d attribute or polygon points
        outline = self._parse_svg_outline(elem, warnings)
        if not outline:
            warnings.append(
                f"Piece '{piece_id}': no outline could be extracted"
            )
            return None

        # Seam allowance
        sa_str = elem.get("data-seam-allowance", "")
        seam_allowance = (
            float(sa_str) if sa_str else _DEFAULT_SEAM_ALLOWANCE
        )

        # Darts from data attributes
        darts = self._parse_svg_darts(elem)

        # Grain line
        grain_line = self._parse_svg_grain_line(elem, outline)

        # Notch marks
        notch_marks = self._parse_svg_notches(elem)

        # Seam lines — derive from outline segments
        seam_lines = self._derive_seam_lines(outline)

        return PatternPiece(
            piece_id=piece_id,
            label=label,
            outline=tuple(outline),
            seam_lines=tuple(seam_lines),
            darts=tuple(darts),
            grain_line=grain_line,
            notch_marks=tuple(notch_marks),
            seam_allowance=seam_allowance,
        )

    @staticmethod
    def _parse_svg_outline(
        elem: ET.Element,
        warnings: list[str],
    ) -> list[Point2D]:
        """Extract outline points from SVG path or polygon."""
        tag = _local_tag(elem.tag)
        points: list[Point2D] = []

        if tag == "polygon":
            pts_str = elem.get("points", "")
            for pair in pts_str.strip().split():
                parts = pair.split(",")
                if len(parts) == 2:
                    points.append(
                        Point2D(float(parts[0]), float(parts[1]))
                    )
            if points and points[0] != points[-1]:
                points.append(points[0])

        elif tag == "path":
            d = elem.get("d", "")
            points = _parse_svg_path_d(d)
            if points and points[0] != points[-1]:
                points.append(points[0])

        return points

    @staticmethod
    def _parse_svg_darts(elem: ET.Element) -> list[DartGeometry]:
        """Parse dart data from SVG data attributes.

        Expected format: data-darts="x,y,angle,length;x,y,angle,length"
        """
        darts_str = elem.get("data-darts", "")
        if not darts_str:
            return []
        darts: list[DartGeometry] = []
        for dart_def in darts_str.split(";"):
            parts = dart_def.strip().split(",")
            if len(parts) == 4:
                darts.append(DartGeometry(
                    apex=Point2D(float(parts[0]), float(parts[1])),
                    angle=float(parts[2]),
                    length=float(parts[3]),
                ))
        return darts

    @staticmethod
    def _parse_svg_grain_line(
        elem: ET.Element,
        outline: list[Point2D],
    ) -> Line2D:
        """Parse grain line from data attribute or derive from outline."""
        gl_str = elem.get("data-grain-line", "")
        if gl_str:
            parts = gl_str.split(",")
            if len(parts) == 4:
                return Line2D(
                    start=Point2D(float(parts[0]), float(parts[1])),
                    end=Point2D(float(parts[2]), float(parts[3])),
                )
        # Default: vertical line through center of bounding box
        if outline:
            xs = [p.x for p in outline]
            ys = [p.y for p in outline]
            cx = (min(xs) + max(xs)) / 2.0
            return Line2D(
                start=Point2D(cx, min(ys) + 1.0),
                end=Point2D(cx, max(ys) - 1.0),
            )
        return Line2D(start=Point2D(0, 0), end=Point2D(0, 1))

    @staticmethod
    def _parse_svg_notches(elem: ET.Element) -> list[Point2D]:
        """Parse notch marks from data attribute.

        Expected format: data-notches="x,y;x,y"
        """
        notch_str = elem.get("data-notches", "")
        if not notch_str:
            return []
        notches: list[Point2D] = []
        for pair in notch_str.split(";"):
            parts = pair.strip().split(",")
            if len(parts) == 2:
                notches.append(
                    Point2D(float(parts[0]), float(parts[1]))
                )
        return notches

    @staticmethod
    def _derive_seam_lines(
        outline: list[Point2D],
    ) -> list[Line2D]:
        """Derive seam lines from consecutive outline points."""
        lines: list[Line2D] = []
        for i in range(len(outline) - 1):
            lines.append(Line2D(start=outline[i], end=outline[i + 1]))
        return lines


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------


def _local_tag(tag: str) -> str:
    """Strip namespace from SVG tag."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _iter_svg_elements(root: ET.Element) -> list[ET.Element]:
    """Find all SVG path/polygon elements with data-piece-id."""
    results: list[ET.Element] = []
    for elem in root.iter():
        if elem.get("data-piece-id"):
            results.append(elem)
    return results


def _parse_svg_path_d(d: str) -> list[Point2D]:
    """Parse a simple SVG path d attribute (M/L/Z commands only).

    Supports absolute M (moveto) and L (lineto) commands.
    Returns empty list for unsupported commands.
    """
    points: list[Point2D] = []
    # Tokenize: split on commands, keeping the command letter
    tokens = re.findall(r'[MLZmlz][^MLZmlz]*', d.strip())
    for token in tokens:
        cmd = token[0].upper()
        if cmd == "Z":
            if points and points[0] != points[-1]:
                points.append(points[0])
            continue
        coords = re.findall(r'[-+]?\d*\.?\d+', token[1:])
        if cmd in ("M", "L"):
            for i in range(0, len(coords) - 1, 2):
                points.append(
                    Point2D(float(coords[i]), float(coords[i + 1]))
                )
    return points
