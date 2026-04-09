"""Skirt 3D visualization generator.

Generates a self-contained Three.js HTML visualization for skirt
patterns, reusing the same template as the bodice html_visualizer.
"""

from __future__ import annotations

import json
import math

from agentic_pattern_engine.models import (
    AuditTrail,
    SkirtMeasurementProfile,
)


def generate_skirt_visualization(
    profile: SkirtMeasurementProfile,
    audit_trail: AuditTrail,
) -> str:
    """Generate a self-contained HTML visualization for a skirt run."""
    from agentic_pattern_engine.html_visualizer import _HTML_TEMPLATE
    from agentic_pattern_engine.skirt_generator import SkirtGarmentSpec

    spec = SkirtGarmentSpec()
    SEGMENTS = 32
    waist_r = profile.waist / (2 * math.pi)
    hip_r = profile.hip / (2 * math.pi)
    hip_d = profile.hip_depth
    length = profile.desired_length

    # Body mesh rings
    ring_specs = [
        (0.0, waist_r),
        (-hip_d * 0.15, waist_r + (hip_r - waist_r) * 0.15),
        (-hip_d * 0.3, waist_r + (hip_r - waist_r) * 0.35),
        (-hip_d * 0.5, waist_r + (hip_r - waist_r) * 0.6),
        (-hip_d * 0.7, waist_r + (hip_r - waist_r) * 0.8),
        (-hip_d * 0.85, waist_r + (hip_r - waist_r) * 0.92),
        (-hip_d, hip_r),
        (-hip_d - (length - hip_d) * 0.15, hip_r * 0.97),
        (-hip_d - (length - hip_d) * 0.3, hip_r * 0.92),
        (-hip_d - (length - hip_d) * 0.5, hip_r * 0.85),
        (-hip_d - (length - hip_d) * 0.7, hip_r * 0.75),
        (-length, hip_r * 0.65),
    ]
    n_rings = len(ring_specs)
    skirt_ring_specs = [
        rs for rs in ring_specs if rs[0] >= -length
    ]
    n_skirt_rings = len(skirt_ring_specs)

    # Body vertices and faces
    body_verts = []
    body_faces = []
    for ri, (y, r) in enumerate(ring_specs):
        for si in range(SEGMENTS):
            theta = (si / SEGMENTS) * 2 * math.pi
            body_verts.append([
                round(math.cos(theta) * r, 3),
                round(y, 3),
                round(math.sin(theta) * r, 3),
            ])
    for ri in range(n_rings - 1):
        for si in range(SEGMENTS):
            i0 = ri * SEGMENTS + si
            i1 = ri * SEGMENTS + (si + 1) % SEGMENTS
            i2 = (ri + 1) * SEGMENTS + si
            i3 = (ri + 1) * SEGMENTS + (si + 1) % SEGMENTS
            body_faces.append([i0, i2, i1])
            body_faces.append([i1, i2, i3])

    # Garment faces
    garment_faces = []
    for ri in range(n_skirt_rings - 1):
        for si in range(SEGMENTS):
            i0 = ri * SEGMENTS + si
            i1 = ri * SEGMENTS + (si + 1) % SEGMENTS
            i2 = (ri + 1) * SEGMENTS + si
            i3 = (ri + 1) * SEGMENTS + (si + 1) % SEGMENTS
            garment_faces.append([i0, i2, i1])
            garment_faces.append([i1, i2, i3])

    # Seam lines
    cf_line = [ri * SEGMENTS for ri in range(n_skirt_rings)]
    cb_line = [
        ri * SEGMENTS + SEGMENTS // 2
        for ri in range(n_skirt_rings)
    ]
    rs_line = [
        ri * SEGMENTS + SEGMENTS // 4
        for ri in range(n_skirt_rings)
    ]
    ls_line = [
        ri * SEGMENTS + 3 * SEGMENTS // 4
        for ri in range(n_skirt_rings)
    ]
    waist_ring = list(range(SEGMENTS)) + [0]
    hem_start = (n_skirt_rings - 1) * SEGMENTS
    hem_ring = (
        list(range(hem_start, hem_start + SEGMENTS))
        + [hem_start]
    )

    seam_lines = {
        "center_front": cf_line,
        "center_back": cb_line,
        "right_side": rs_line,
        "left_side": ls_line,
        "right_shoulder": waist_ring,
        "left_shoulder": hem_ring,
        "right_princess": [],
        "left_princess": [],
    }

    def _build_garment_verts(pieces):
        if not pieces:
            return _default_garment_verts()
        front = pieces[0]
        front_w = (
            max(p.x for p in front.outline)
            - min(p.x for p in front.outline)
        )
        g_waist_r = waist_r + 0.8
        g_hip_r = hip_r + 1.2
        max_y = max(p.y for p in front.outline)
        hem_pts = [
            p for p in front.outline if abs(p.y - max_y) < 3
        ]
        hem_half_w = (
            max(p.x for p in hem_pts) if hem_pts else front_w * 1.3
        )
        g_hem_r = (hem_half_w * 2) / math.pi + 2.0

        verts = []
        for y, body_r in skirt_ring_specs:
            t = abs(y) / length if length > 0 else 0
            hip_t_norm = hip_d / length if length > 0 else 0.3
            if t <= hip_t_norm:
                frac = t / hip_t_norm
                frac = frac * frac * (3 - 2 * frac)
                r = g_waist_r + (g_hip_r - g_waist_r) * frac
            else:
                frac = (t - hip_t_norm) / (1 - hip_t_norm)
                r = g_hip_r + (g_hem_r - g_hip_r) * frac
            for si in range(SEGMENTS):
                theta = (si / SEGMENTS) * 2 * math.pi
                verts.append([
                    round(math.cos(theta) * r, 3),
                    round(y, 3),
                    round(math.sin(theta) * r, 3),
                ])
        return verts

    def _default_garment_verts():
        verts = []
        for y, body_r in skirt_ring_specs:
            r = body_r + 1.2
            for si in range(SEGMENTS):
                theta = (si / SEGMENTS) * 2 * math.pi
                verts.append([
                    round(math.cos(theta) * r, 3),
                    round(y, 3),
                    round(math.sin(theta) * r, 3),
                ])
        return verts

    # Build iteration data
    def _compute_skirt_dart_lines(pieces, gv, segs, n_sr, w_r, ln):
        """Compute 3D dart V-lines mirrored on both sides."""
        if not pieces:
            return []
        lines = []
        for pi, piece in enumerate(pieces):
            pw = max(p.x for p in piece.outline)
            for dart in piece.darts:
                frac = dart.apex.x / pw if pw > 0 else 0.5
                if pi == 0:
                    angles = [
                        frac * (math.pi / 2),
                        2 * math.pi - frac * (math.pi / 2),
                    ]
                else:
                    angles = [
                        math.pi / 2 + frac * (math.pi / 2),
                        math.pi + (math.pi / 2 - frac * (math.pi / 2)),
                    ]
                for ba in angles:
                    if len(gv) > 0:
                        ar = math.sqrt(gv[0][0]**2 + gv[0][2]**2)
                    else:
                        ar = w_r + 2
                    apex = [
                        round(math.cos(ba) * (ar + 0.3), 3),
                        0.0,
                        round(math.sin(ba) * (ar + 0.3), 3),
                    ]
                    ha = math.radians(dart.angle / 2)
                    ly = -dart.length
                    t = dart.length / ln if ln > 0 else 0.3
                    tr = min(int(t * n_sr), n_sr - 1)
                    tb = tr * segs
                    if tb < len(gv):
                        tip_r = math.sqrt(
                            gv[tb][0]**2 + gv[tb][2]**2,
                        )
                    else:
                        tip_r = ar
                    leg1 = [
                        round(math.cos(ba - ha) * (tip_r + 0.3), 3),
                        round(ly, 3),
                        round(math.sin(ba - ha) * (tip_r + 0.3), 3),
                    ]
                    leg2 = [
                        round(math.cos(ba + ha) * (tip_r + 0.3), 3),
                        round(ly, 3),
                        round(math.sin(ba + ha) * (tip_r + 0.3), 3),
                    ]
                    lines.append({
                        "apex": apex, "leg1": leg1, "leg2": leg2,
                    })
        return lines

    iterations_data = []
    for entry in audit_trail.entries:
        pieces = entry.pieces or []
        gv = _build_garment_verts(pieces)
        n_gv = len(gv)

        stresses = [0.0] * n_gv
        regional = {}
        if entry.iteration > 0 and pieces:
            regional = spec.compute_stress(pieces, profile)
            avg = sum(regional.values()) / max(len(regional), 1)
            # Only show stress color for non-converged iterations
            if entry.fit_issues:
                for vi in range(n_gv):
                    seg_idx = vi % SEGMENTS
                    is_back = seg_idx >= SEGMENTS // 2
                    stresses[vi] = avg * (1.3 if is_back else 0.7)

        front_darts = []
        if pieces:
            for d in pieces[0].darts:
                front_darts.append({
                    "angle": round(d.angle, 2),
                    "length": round(d.length, 2),
                })

        dart_lines = _compute_skirt_dart_lines(
            pieces, gv, SEGMENTS, n_skirt_rings,
            waist_r, length,
        )

        iterations_data.append({
            "iteration": entry.iteration,
            "stresses": [round(s, 2) for s in stresses],
            "garment_vertices": gv,
            "total_stress": round(
                entry.total_stress_magnitude, 1,
            ),
            "regional_stresses": {
                k: round(v, 1) for k, v in regional.items()
            },
            "fit_issues": [
                {
                    "region": i.region.value,
                    "type": i.issue_type.value,
                    "stress": round(i.measured_stress, 1),
                    "threshold": round(i.threshold, 1),
                }
                for i in entry.fit_issues
            ],
            "bust_ease": 0.0,
            "waist_ease": 0.0,
            "n_corrections": len(entry.corrections_applied),
            "front_darts": front_darts,
            "dart_lines_3d": dart_lines,
        })

    mannequin = {
        "torso_top_y": 0.0,
        "shoulder_half_width": 0.0,
        "neck_radius": 0.0,
        "neck_height": 0.0,
        "head_radius": 0.0,
        "arm_radius": 0.0,
        "arm_length": 0.0,
    }

    data = {
        "body_vertices": body_verts,
        "body_faces": body_faces,
        "garment_faces": garment_faces,
        "mannequin": mannequin,
        "seam_lines": seam_lines,
        "iterations": iterations_data,
        "max_stress": max(
            (max(it["stresses"]) if it["stresses"] else 0)
            for it in iterations_data
        ),
    }

    html = _HTML_TEMPLATE.replace(
        "MANI — Agentic Pattern Engine Visualization",
        "MANI — Skirt Pattern Visualization",
    ).replace(
        "Bodice drape simulation · cloth view",
        f"A-line skirt · W {profile.waist}cm "
        f"H {profile.hip}cm L {profile.desired_length}cm",
    ).replace(
        "Front bust dart",
        "Waist dart",
    )

    # Inject CF/CB/SS/FRONT/BACK labels
    label_js = f"""
// --- 3D Text Labels ---
function makeLabel(text, color) {{
  var c = document.createElement('canvas');
  c.width = 128; c.height = 64;
  var ctx = c.getContext('2d');
  ctx.fillStyle = color || '#fff';
  ctx.font = 'bold 36px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, 64, 32);
  var tex = new THREE.CanvasTexture(c);
  var mat = new THREE.SpriteMaterial({{map: tex, depthTest: false}});
  var s = new THREE.Sprite(mat);
  s.scale.set(6, 3, 1);
  return s;
}}
var gv0 = DATA.iterations[0].garment_vertices;
if (gv0 && gv0.length > 0) {{
  var S = {SEGMENTS};
  var cf = gv0[0];
  var l1 = makeLabel('CF', '#4fc3f7');
  l1.position.set(cf[0]*1.3, cf[1]+3, cf[2]*1.3);
  scene.add(l1);
  var cb = gv0[Math.floor(S/2)];
  var l2 = makeLabel('CB', '#ff8a65');
  l2.position.set(cb[0]*1.3, cb[1]+3, cb[2]*1.3);
  scene.add(l2);
  var rs = gv0[Math.floor(S/4)];
  var l3 = makeLabel('SS', '#aaa');
  l3.position.set(rs[0]*1.3, rs[1]+3, rs[2]*1.3);
  scene.add(l3);
  var ls = gv0[Math.floor(3*S/4)];
  var l4 = makeLabel('SS', '#aaa');
  l4.position.set(ls[0]*1.3, ls[1]+3, ls[2]*1.3);
  scene.add(l4);
  var mr = Math.floor({n_skirt_rings}/2);
  var fm = gv0[mr*S];
  var l5 = makeLabel('FRONT', '#4fc3f7');
  l5.position.set(fm[0]*1.4, fm[1], fm[2]*1.4);
  l5.scale.set(8, 4, 1);
  scene.add(l5);
  var bm = gv0[mr*S + Math.floor(S/2)];
  var l6 = makeLabel('BACK', '#ff8a65');
  l6.position.set(bm[0]*1.4, bm[1], bm[2]*1.4);
  l6.scale.set(8, 4, 1);
  scene.add(l6);
}}
"""
    html = html.replace("__DATA__", json.dumps(data))
    html = html.replace(
        "</script>\n</body>",
        label_js + "\n</script>\n</body>",
    )
    return html
