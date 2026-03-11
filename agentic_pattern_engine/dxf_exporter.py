"""DXF Exporter — export BodiceSloper to DXF format using ezdxf.

Each pattern piece gets its own named layer. Includes closed polyline
outlines, seam lines, dart lines, grain lines, notch marks, seam
allowance markings, piece labels, and metadata in custom properties.
Also supports round-trip parsing back to BodiceSloper.
"""

from __future__ import annotations

import io
import json
from typing import Any

import ezdxf
from ezdxf.document import Drawing

from agentic_pattern_engine.models import (
    BodiceSloper,
    DartGeometry,
    ExportMetadata,
    Line2D,
    MeasurementProfile,
    PatternPiece,
    Point2D,
)

# DXF layer color indices
_COLORS = {"front_bodice": 1, "back_bodice": 3}  # red, green
# Element type markers stored in XDATA or as text prefixes
_ELEMENT_PREFIX = {
    "outline": "OL",
    "seam": "SL",
    "dart": "DT",
    "grain": "GL",
    "notch": "NM",
    "seam_allowance": "SA",
    "label": "LB",
}


class DXFPatternExporter:
    """Export and parse BodiceSloper patterns in DXF format."""

    def export(
        self,
        sloper: BodiceSloper,
        metadata: ExportMetadata,
    ) -> bytes:
        """Export sloper to DXF with pieces on named layers."""
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()

        # Store metadata as custom properties in the document header
        doc.header.custom_vars.append("MANI_PROFILE_HASH", metadata.profile_hash)
        doc.header.custom_vars.append("MANI_RUN_ID", metadata.run_id)
        doc.header.custom_vars.append("MANI_ITER_COUNT", str(metadata.iteration_count))
        doc.header.custom_vars.append("MANI_STATUS", metadata.convergence_status)

        # Store sloper-level data as JSON in a custom var
        sloper_meta = json.dumps({
            "sloper_id": sloper.sloper_id,
            "bust_ease": sloper.bust_ease,
            "waist_ease": sloper.waist_ease,
            "profile": {
                "chest": sloper.profile.chest,
                "waist": sloper.profile.waist,
                "hip": sloper.profile.hip,
                "shoulder_width": sloper.profile.shoulder_width,
                "torso_length": sloper.profile.torso_length,
            },
        })
        doc.header.custom_vars.append("MANI_SLOPER_META", sloper_meta)

        for piece, layer_name in [
            (sloper.front_bodice, "front_bodice"),
            (sloper.back_bodice, "back_bodice"),
        ]:
            color = _COLORS[layer_name]
            doc.layers.add(layer_name, color=color)
            self._write_piece(msp, piece, layer_name)

        stream = io.StringIO()
        doc.write(stream)
        return stream.getvalue().encode("utf-8")

    def parse(self, dxf_bytes: bytes) -> BodiceSloper:
        """Parse DXF back to BodiceSloper for round-trip verification."""
        stream = io.StringIO(dxf_bytes.decode("utf-8"))
        doc = ezdxf.read(stream)
        msp = doc.modelspace()

        # Read sloper metadata
        sloper_meta_str = _get_custom_var(doc, "MANI_SLOPER_META")
        sloper_meta = json.loads(sloper_meta_str) if sloper_meta_str else {}

        profile = MeasurementProfile(
            chest=sloper_meta.get("profile", {}).get("chest", 0.0),
            waist=sloper_meta.get("profile", {}).get("waist", 0.0),
            hip=sloper_meta.get("profile", {}).get("hip", 0.0),
            shoulder_width=sloper_meta.get("profile", {}).get("shoulder_width", 0.0),
            torso_length=sloper_meta.get("profile", {}).get("torso_length", 0.0),
        )

        front = self._read_piece(msp, "front_bodice", "Front Bodice")
        back = self._read_piece(msp, "back_bodice", "Back Bodice")

        return BodiceSloper(
            sloper_id=sloper_meta.get("sloper_id", "parsed"),
            profile=profile,
            front_bodice=front,
            back_bodice=back,
            bust_ease=sloper_meta.get("bust_ease", 0.0),
            waist_ease=sloper_meta.get("waist_ease", 0.0),
            metadata={"source": "dxf_parse"},
        )

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def _write_piece(
        self,
        msp: Any,
        piece: PatternPiece,
        layer_name: str,
    ) -> None:
        """Write a single pattern piece to the DXF modelspace."""
        # Outline as closed polyline
        if piece.outline:
            pts = [(p.x, p.y) for p in piece.outline]
            poly = msp.add_lwpolyline(pts, dxfattribs={"layer": layer_name})
            poly.close()

        # Seam lines
        for sl in piece.seam_lines:
            msp.add_line(
                (sl.start.x, sl.start.y),
                (sl.end.x, sl.end.y),
                dxfattribs={"layer": layer_name, "linetype": "DASHED"},
            )

        # Darts — draw as two lines from apex
        for dart in piece.darts:
            import math
            half_angle = dart.angle / 2.0
            rad1 = math.radians(-half_angle)
            rad2 = math.radians(half_angle)
            end1 = (
                dart.apex.x + dart.length * math.cos(rad1),
                dart.apex.y + dart.length * math.sin(rad1),
            )
            end2 = (
                dart.apex.x + dart.length * math.cos(rad2),
                dart.apex.y + dart.length * math.sin(rad2),
            )
            msp.add_line(
                (dart.apex.x, dart.apex.y), end1,
                dxfattribs={"layer": layer_name},
            )
            msp.add_line(
                (dart.apex.x, dart.apex.y), end2,
                dxfattribs={"layer": layer_name},
            )
            # Store dart metadata as text
            msp.add_text(
                f"DT:{dart.angle:.4f}:{dart.length:.4f}",
                dxfattribs={
                    "layer": layer_name,
                    "insert": (dart.apex.x, dart.apex.y),
                    "height": 0.5,
                },
            )

        # Grain line
        gl = piece.grain_line
        msp.add_line(
            (gl.start.x, gl.start.y),
            (gl.end.x, gl.end.y),
            dxfattribs={"layer": layer_name, "color": 5},
        )

        # Notch marks as points
        for nm in piece.notch_marks:
            msp.add_point(
                (nm.x, nm.y),
                dxfattribs={"layer": layer_name},
            )

        # Seam allowance as text annotation
        msp.add_text(
            f"SA:{piece.seam_allowance:.4f}",
            dxfattribs={
                "layer": layer_name,
                "insert": (0, 0),
                "height": 0.5,
            },
        )

        # Piece label
        msp.add_text(
            f"LB:{piece.label}",
            dxfattribs={
                "layer": layer_name,
                "insert": (0, -2),
                "height": 1.0,
            },
        )

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def _read_piece(
        self,
        msp: Any,
        layer_name: str,
        default_label: str,
    ) -> PatternPiece:
        """Read a pattern piece from DXF entities on a named layer."""
        outline_pts: list[Point2D] = []
        seam_lines: list[Line2D] = []
        darts: list[DartGeometry] = []
        grain_line: Line2D | None = None
        notch_marks: list[Point2D] = []
        seam_allowance = 1.5
        label = default_label

        for entity in msp:
            if entity.dxf.layer != layer_name:
                continue

            if entity.dxftype() == "LWPOLYLINE":
                # This is the outline
                with entity.points("xy") as pts:
                    outline_pts = [Point2D(x=p[0], y=p[1]) for p in pts]
                # Ensure closed
                if outline_pts and outline_pts[0] != outline_pts[-1]:
                    outline_pts.append(outline_pts[0])

            elif entity.dxftype() == "POINT":
                notch_marks.append(
                    Point2D(x=entity.dxf.location.x, y=entity.dxf.location.y)
                )

            elif entity.dxftype() == "TEXT":
                text = entity.dxf.text
                if text.startswith("DT:"):
                    parts = text.split(":")
                    if len(parts) == 3:
                        angle = float(parts[1])
                        length = float(parts[2])
                        ins = entity.dxf.insert
                        darts.append(DartGeometry(
                            apex=Point2D(x=ins.x, y=ins.y),
                            angle=angle,
                            length=length,
                        ))
                elif text.startswith("SA:"):
                    seam_allowance = float(text[3:])
                elif text.startswith("LB:"):
                    label = text[3:]

            elif entity.dxftype() == "LINE":
                start = entity.dxf.start
                end = entity.dxf.end
                line = Line2D(
                    start=Point2D(x=start.x, y=start.y),
                    end=Point2D(x=end.x, y=end.y),
                )
                # Distinguish grain line (color=5) from seam lines
                color = entity.dxf.get("color", 256)
                if color == 5 and grain_line is None:
                    grain_line = line
                else:
                    seam_lines.append(line)

        if grain_line is None:
            grain_line = Line2D(start=Point2D(0, 0), end=Point2D(0, 1))

        return PatternPiece(
            piece_id=layer_name.replace("_bodice", ""),
            label=label,
            outline=tuple(outline_pts) if outline_pts else (Point2D(0, 0), Point2D(0, 0)),
            seam_lines=tuple(seam_lines),
            darts=tuple(darts),
            grain_line=grain_line,
            notch_marks=tuple(notch_marks),
            seam_allowance=seam_allowance,
        )


def _get_custom_var(doc: Drawing, name: str) -> str | None:
    """Read a custom header variable from the DXF document."""
    for tag_name, value in doc.header.custom_vars:
        if tag_name == name:
            return value
    return None
