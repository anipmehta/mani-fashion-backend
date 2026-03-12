"""HTML/Three.js visualizer for the agentic pattern engine.

Generates a self-contained HTML file that shows:
- A mannequin body with head, neck, and arm stubs (visual only)
- A garment shell mesh draped on the body, colored by per-region tension
- Garment shell offset scales with ease (visibly loosens as corrections apply)
- Seam lines, princess lines, and dart V-lines on the garment surface
- Per-iteration stats panel with dart angles, ease, and regional stress
- A slider / play button to scrub through self-correction iterations

Open the resulting HTML in any modern browser.
"""

from __future__ import annotations

import json
import math

import numpy as np

from agentic_pattern_engine.models import (
    AuditTrail,
    BodyModel,
    TensionThresholds,
)
from agentic_pattern_engine.simulation_engine import MassSpringSimulationEngine


# Base garment offset from body surface (cm)
_BASE_GARMENT_OFFSET = 0.8
# Extra offset per cm of ease — amplified so changes are visible
_EASE_OFFSET_SCALE = 0.15


def _build_garment_shell_for_iteration(
    body_model: BodyModel,
    bust_ease: float,
    waist_ease: float,
) -> list[list[float]]:
    """Build garment shell vertices with offset that scales with ease."""
    bv = body_model.vertices
    n_body = len(bv)

    y_values = sorted(set(round(float(v[1]), 4) for v in bv))
    n_rings = len(y_values)
    pts_per_ring = n_body // n_rings if n_rings > 0 else 20

    ring_ease = []
    for ri, yv in enumerate(y_values):
        t = ri / max(n_rings - 1, 1)
        if t < 0.4:
            ease = waist_ease * (t / 0.4)
        elif t < 0.8:
            ease = waist_ease + (bust_ease - waist_ease) * ((t - 0.4) / 0.4)
        else:
            ease = bust_ease * (1.0 - (t - 0.8) / 0.2) * 0.5
        ring_ease.append(ease)

    garment_verts: list[list[float]] = []
    for vi in range(n_body):
        pt = bv[vi].copy()
        ring_idx = vi // pts_per_ring
        ease = ring_ease[min(ring_idx, len(ring_ease) - 1)]
        offset = _BASE_GARMENT_OFFSET + ease * _EASE_OFFSET_SCALE

        radial = np.array([pt[0], 0.0, pt[2]])
        norm = np.linalg.norm(radial)
        if norm > 1e-6:
            pt += (radial / norm) * offset
        garment_verts.append(pt.tolist())

    return garment_verts


def _build_garment_faces(body_model: BodyModel) -> list[list[int]]:
    """Build garment face indices (same topology for all iterations)."""
    bv = body_model.vertices
    n_body = len(bv)
    y_values = sorted(set(round(float(v[1]), 4) for v in bv))
    n_rings = len(y_values)
    pts_per_ring = n_body // n_rings if n_rings > 0 else 20

    faces: list[list[int]] = []
    for ring in range(n_rings - 1):
        for i in range(pts_per_ring):
            a = ring * pts_per_ring + i
            b = ring * pts_per_ring + (i + 1) % pts_per_ring
            c = (ring + 1) * pts_per_ring + i
            d = (ring + 1) * pts_per_ring + (i + 1) % pts_per_ring
            faces.append([a, c, b])
            faces.append([b, c, d])
    return faces


def _vertex_region_stress(
    body_model: BodyModel,
    regional_stresses: dict[str, float],
) -> list[float]:
    """Map regional stress values to per-vertex stress for the garment shell."""
    bv = body_model.vertices
    n = len(bv)
    fr = body_model.fit_regions

    region_map: dict[int, str] = {}
    for name in ("bust", "waist", "shoulder", "armhole",
                 "side_seam", "center_front", "center_back"):
        indices = getattr(fr, name)
        for idx in indices:
            region_map[int(idx)] = name

    stresses = []
    avg_stress = (sum(regional_stresses.values()) / len(regional_stresses)
                  if regional_stresses else 0.0)
    for i in range(n):
        region = region_map.get(i)
        if region and region in regional_stresses:
            stresses.append(regional_stresses[region])
        else:
            stresses.append(avg_stress)
    return stresses


def _compute_dart_lines_3d(
    sloper: "BodiceSloper",
    garment_verts: list[list[float]],
    n_rings: int,
    pts_per_ring: int,
    y_values: list[float],
    y_min: float,
    y_range: float,
    profile: "MeasurementProfile",
) -> list[dict]:
    """Compute 3D V-shaped dart lines for front and back bodice.

    Each dart is returned as {"label": str, "apex": [x,y,z],
    "leg1": [x,y,z], "leg2": [x,y,z], "side": "front"|"back"}.
    """
    results: list[dict] = []
    torso_length = profile.torso_length

    for side, piece, labels in [
        ("front", sloper.front_bodice, ["Front bust dart", "Front waist dart"]),
        ("back", sloper.back_bodice, ["Back shoulder dart", "Back dart 2"]),
    ]:
        width_2d = piece.outline[2].x if len(piece.outline) > 2 else 10.0
        for di, dart in enumerate(piece.darts):
            label = labels[di] if di < len(labels) else f"{side} dart {di+1}"

            # Map 2D apex y to ring index
            frac_from_top = min(max(-dart.apex.y / torso_length, 0.0), 1.0)
            ring_idx = int(round((1.0 - frac_from_top) * (n_rings - 1)))
            ring_idx = max(0, min(ring_idx, n_rings - 1))

            # Map 2D apex x to angular position within the ring
            # Front: CF=vertex 0, side seam=pts_per_ring//4
            # Back: CB=pts_per_ring//2, side seam going toward pts_per_ring//4
            x_frac = min(max(dart.apex.x / width_2d, 0.0), 1.0) if width_2d > 0 else 0.5
            if side == "front":
                vert_in_ring = int(round(x_frac * (pts_per_ring // 4)))
            else:
                # Back: x=0 is CB (vertex pts_per_ring//2), x=width is side seam.
                # Go from CB toward the right side seam (decreasing vertex index
                # toward pts_per_ring//4) so the dart lands on the +z (right) side.
                vert_in_ring = pts_per_ring // 2 - int(round(x_frac * (pts_per_ring // 4)))

            apex_vi = ring_idx * pts_per_ring + max(0, min(vert_in_ring, pts_per_ring - 1))
            if apex_vi >= len(garment_verts):
                continue
            apex_pt = garment_verts[apex_vi]

            # Amplified leg length so dart V is clearly visible on the garment.
            # Use a minimum of 4cm and scale with dart angle for visual impact.
            leg_len_3d = max(4.0, dart.length * 1.2)
            half_angle_rad = math.radians(dart.angle / 2.0)

            # Get tangent direction from neighboring vertex in the same ring
            neighbor_offset = 1 if side == "front" else -1
            neighbor_vi = ring_idx * pts_per_ring + max(0, min(
                vert_in_ring + neighbor_offset, pts_per_ring - 1))
            if neighbor_vi >= len(garment_verts):
                neighbor_vi = apex_vi

            n_pt = garment_verts[neighbor_vi]
            tangent = np.array([n_pt[0] - apex_pt[0], 0.0, n_pt[2] - apex_pt[2]])
            t_norm = np.linalg.norm(tangent)
            if t_norm > 1e-6:
                tangent = tangent / t_norm
            else:
                tangent = np.array([1.0, 0.0, 0.0])

            down = np.array([0.0, -1.0, 0.0])
            leg1_dir = down * math.cos(half_angle_rad) + tangent * math.sin(half_angle_rad)
            leg2_dir = down * math.cos(half_angle_rad) - tangent * math.sin(half_angle_rad)

            apex_arr = np.array(apex_pt)
            leg1_end = apex_arr + leg1_dir * leg_len_3d
            leg2_end = apex_arr + leg2_dir * leg_len_3d

            # Offset outward from body center so dart lines sit on cloth surface
            radial = np.array([apex_pt[0], 0.0, apex_pt[2]])
            rn = np.linalg.norm(radial)
            if rn > 1e-6:
                outward = radial / rn * 0.4
                apex_arr = apex_arr + outward
                leg1_end = leg1_end + outward
                leg2_end = leg2_end + outward

            results.append({
                "label": label, "side": side,
                "apex": [round(float(v), 3) for v in apex_arr],
                "leg1": [round(float(v), 3) for v in leg1_end],
                "leg2": [round(float(v), 3) for v in leg2_end],
            })

    # Mirror all darts to the opposite side.
    # The body cylinder has left/right symmetry across the z=0 plane:
    #   CF at +x, CB at -x, right side at +z, left side at -z.
    # So mirroring flips z, not x.
    mirrored = []
    for d in results:
        mirrored.append({
            "label": d["label"] + " (L)", "side": d["side"],
            "apex": [d["apex"][0], d["apex"][1], -d["apex"][2]],
            "leg1": [d["leg1"][0], d["leg1"][1], -d["leg1"][2]],
            "leg2": [d["leg2"][0], d["leg2"][1], -d["leg2"][2]],
        })
    results.extend(mirrored)
    return results


def generate_visualization(
    body_model: BodyModel,
    audit_trail: AuditTrail,
    thresholds: TensionThresholds | None = None,
) -> str:
    """Generate a self-contained HTML visualization."""
    sim = MassSpringSimulationEngine()
    thresholds = thresholds or TensionThresholds()

    body_verts = body_model.vertices.tolist()
    body_faces = body_model.faces.tolist()
    garment_faces = _build_garment_faces(body_model)

    profile = body_model.profile
    bv = body_model.vertices
    torso_top_y = float(bv[:, 1].max())
    shoulder_half = profile.shoulder_width / 2.0

    mannequin = {
        "torso_top_y": round(torso_top_y, 2),
        "shoulder_half_width": round(shoulder_half, 2),
        "neck_radius": round(profile.shoulder_width * 0.12, 2),
        "neck_height": round(profile.torso_length * 0.12, 2),
        "head_radius": round(profile.shoulder_width * 0.22, 2),
        "arm_radius": round(profile.shoulder_width * 0.08, 2),
        "arm_length": round(profile.torso_length * 0.45, 2),
    }

    n_body = len(bv)
    y_values = sorted(set(round(float(v[1]), 4) for v in bv))
    n_rings = len(y_values)
    pts_per_ring = n_body // n_rings if n_rings > 0 else 20

    cf_line = [ring * pts_per_ring for ring in range(n_rings)]
    cb_line = [ring * pts_per_ring + pts_per_ring // 2 for ring in range(n_rings)]
    rs_line = [ring * pts_per_ring + pts_per_ring // 4 for ring in range(n_rings)]
    ls_line = [ring * pts_per_ring + 3 * pts_per_ring // 4 for ring in range(n_rings)]
    shoulder_ring_start = (n_rings - 1) * pts_per_ring
    r_shoulder = list(range(shoulder_ring_start, shoulder_ring_start + pts_per_ring // 4 + 1))
    l_shoulder = [shoulder_ring_start] + list(range(
        shoulder_ring_start + pts_per_ring - 1,
        shoulder_ring_start + 3 * pts_per_ring // 4 - 1, -1))

    # Princess lines pass through the dart apex angular position.
    # Front bust dart apex is at x = width * 0.6 on the front piece,
    # which maps to vertex offset = 0.6 * (pts_per_ring // 4) from CF.
    # Back shoulder dart apex is at x = shoulder_half * 0.5 on the back piece,
    # which maps from CB toward the side seam.
    front_width = profile.chest / 4.0 + 2.5  # approximate front width
    front_bust_x_frac = 0.6  # from _draft_front: bust_dart_apex x = width * 0.6
    front_princess_offset = max(1, int(round(front_bust_x_frac * (pts_per_ring // 4))))

    rp_line = [ring * pts_per_ring + front_princess_offset for ring in range(n_rings)]
    lp_line = [ring * pts_per_ring + pts_per_ring - front_princess_offset for ring in range(n_rings)]

    seam_lines = {
        "center_front": cf_line, "center_back": cb_line,
        "right_side": rs_line, "left_side": ls_line,
        "right_shoulder": r_shoulder, "left_shoulder": l_shoulder,
        "right_princess": rp_line, "left_princess": lp_line,
    }

    iterations_data: list[dict] = []
    max_stress = 0.0
    y_min = float(bv[:, 1].min())
    y_max = float(bv[:, 1].max())
    y_range = y_max - y_min if y_max > y_min else 1.0

    for entry in audit_trail.entries:
        sloper = entry.sloper
        regional = sim._compute_regional_stresses(sloper, body_model.profile)
        vertex_stresses = _vertex_region_stress(body_model, regional)
        local_max = max(vertex_stresses) if vertex_stresses else 0.0
        if local_max > max_stress:
            max_stress = local_max

        garment_verts = _build_garment_shell_for_iteration(
            body_model, sloper.bust_ease, sloper.waist_ease,
        )

        if entry.iteration == 0 and not entry.fit_issues:
            from agentic_pattern_engine.fit_detector import TensionFitDetector
            detector = TensionFitDetector()
            sim_result = sim.simulate(sloper, body_model)
            detected = detector.detect(sim_result.tension_map, body_model, thresholds)
            issues = [{"region": fi.region.value, "type": fi.issue_type.value,
                       "stress": round(fi.measured_stress, 1), "threshold": round(fi.threshold, 1)}
                      for fi in detected]
        else:
            issues = [{"region": fi.region.value, "type": fi.issue_type.value,
                       "stress": round(fi.measured_stress, 1), "threshold": round(fi.threshold, 1)}
                      for fi in entry.fit_issues]

        computed_total = sum(
            max(0.0, regional.get(r, 0.0) - getattr(thresholds, r, 500.0))
            for r in ("bust", "waist", "shoulder", "armhole",
                      "side_seam", "center_front", "center_back")
        )
        display_total = round(computed_total, 1) if entry.iteration == 0 else round(entry.total_stress_magnitude, 1)

        front_darts = [{"angle": round(d.angle, 2), "length": round(d.length, 2)}
                       for d in sloper.front_bodice.darts]
        back_darts = [{"angle": round(d.angle, 2), "length": round(d.length, 2)}
                      for d in sloper.back_bodice.darts]

        dart_lines_3d = _compute_dart_lines_3d(
            sloper, garment_verts, n_rings, pts_per_ring,
            y_values, y_min, y_range, profile,
        )

        iterations_data.append({
            "iteration": entry.iteration,
            "stresses": [round(s, 2) for s in vertex_stresses],
            "garment_vertices": garment_verts,
            "total_stress": display_total,
            "regional_stresses": {k: round(v, 1) for k, v in regional.items()},
            "fit_issues": issues,
            "bust_ease": round(sloper.bust_ease, 2),
            "waist_ease": round(sloper.waist_ease, 2),
            "n_corrections": len(entry.corrections_applied),
            "front_darts": front_darts,
            "back_darts": back_darts,
            "dart_lines_3d": dart_lines_3d,
        })

    data = {
        "body_vertices": body_verts,
        "body_faces": body_faces,
        "garment_faces": garment_faces,
        "mannequin": mannequin,
        "seam_lines": seam_lines,
        "iterations": iterations_data,
        "max_stress": round(max_stress, 1),
    }

    return _HTML_TEMPLATE.replace("__DATA__", json.dumps(data))


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>MANI — Agentic Pattern Engine Visualization</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #1a1a2e; color: #eee; font-family: system-ui, sans-serif; overflow: hidden; }
  #container { width: 100vw; height: 100vh; }
  #controls {
    position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%);
    background: rgba(0,0,0,0.85); padding: 16px 24px; border-radius: 12px;
    display: flex; flex-direction: column; align-items: center; gap: 8px;
    min-width: 620px; backdrop-filter: blur(8px);
  }
  .info { font-size: 13px; opacity: 0.9; }
  .info b { color: #4fc3f7; }
  #issues { font-size: 12px; color: #ffab91; max-height: 60px; overflow-y: auto; width: 100%; }
  #legend {
    position: absolute; top: 20px; right: 20px;
    background: rgba(0,0,0,0.85); padding: 12px 16px; border-radius: 8px;
    font-size: 12px; backdrop-filter: blur(8px);
  }
  .legend-bar {
    width: 150px; height: 16px; border-radius: 4px;
    background: linear-gradient(to right, #f5f0e1, #e8c170, #d4763a, #c62828);
    margin: 4px 0;
  }
  .legend-labels { display: flex; justify-content: space-between; font-size: 11px; }
  h3 { font-size: 14px; margin-bottom: 4px; color: #4fc3f7; }
  #title {
    position: absolute; top: 20px; left: 20px;
    background: rgba(0,0,0,0.85); padding: 12px 16px; border-radius: 8px;
    backdrop-filter: blur(8px);
  }
  #title h2 { font-size: 16px; color: #4fc3f7; margin-bottom: 2px; }
  #title p { font-size: 11px; opacity: 0.7; }
  .converged { color: #69f0ae !important; }
  #stats-panel {
    position: absolute; top: 20px; left: 50%; transform: translateX(-50%);
    background: rgba(0,0,0,0.85); padding: 12px 16px; border-radius: 8px;
    backdrop-filter: blur(8px); font-size: 12px; min-width: 400px;
  }
  #stats-panel h3 { margin-bottom: 6px; }
  .dart-row { display: flex; gap: 16px; margin: 3px 0; }
  .dart-label { color: #b0bec5; min-width: 100px; }
  .dart-val { color: #4fc3f7; font-family: monospace; }
  .dart-bar { height: 6px; border-radius: 3px; background: #4fc3f7; transition: width 0.3s; }
  .dart-bar-bg { height: 6px; border-radius: 3px; background: #263238; width: 120px; margin-top: 2px; }
  .ease-change { font-size: 11px; color: #69f0ae; margin-left: 4px; }
  #play-btn {
    background: #4fc3f7; color: #1a1a2e; border: none; border-radius: 6px;
    padding: 4px 16px; cursor: pointer; font-size: 12px; font-weight: 600;
  }
  #play-btn:hover { background: #81d4fa; }
  .seam-legend { margin-top: 10px; border-top: 1px solid #333; padding-top: 8px; }
  .seam-legend-item { display: flex; align-items: center; gap: 6px; margin: 2px 0; }
  .seam-swatch { width: 20px; height: 3px; border-radius: 2px; }
  .seam-swatch.dashed { border-top: 2px dashed; background: none !important; }
</style>
</head>
<body>
<div id="container"></div>
<div id="title">
  <h2>MANI Agentic Pattern Engine</h2>
  <p>Bodice drape simulation · cloth view</p>
  <p style="margin-top:4px">Drag to rotate · Scroll to zoom · Arrow keys or Play to scrub</p>
</div>
<div id="legend">
  <h3>Tension (cloth tint)</h3>
  <div class="legend-bar"></div>
  <div class="legend-labels"><span>0 Pa (muslin)</span><span id="max-label">500 Pa</span></div>
  <div style="margin-top:6px; font-size:11px; opacity:0.7">
    <div>Muslin base = no tension</div>
    <div>Warm tint = mild tension</div>
    <div>Orange/Red = excess tension</div>
  </div>
  <div class="seam-legend">
    <div style="font-size:12px; color:#4fc3f7; margin-bottom:4px;">Construction Lines</div>
    <div class="seam-legend-item"><span class="seam-swatch" style="background:#1a237e;"></span> Center front / back</div>
    <div class="seam-legend-item"><span class="seam-swatch" style="background:#1a237e;"></span> Side seams</div>
    <div class="seam-legend-item"><span class="seam-swatch" style="background:#bf360c;"></span> Shoulder seams</div>
    <div class="seam-legend-item"><span class="seam-swatch dashed" style="border-color:#4a148c;"></span> Princess lines</div>
    <div class="seam-legend-item"><span class="seam-swatch" style="background:#e65100;"></span> Dart lines (V)</div>
  </div>
</div>
<div id="stats-panel">
  <h3>Pattern Geometry</h3>
  <div id="dart-info"></div>
</div>
<div id="controls">
  <div class="info">
    Iteration: <b id="iter-num">0</b> / <b id="iter-max">0</b>
    &nbsp;|&nbsp; Total violation: <b id="total-stress">0</b> Pa
    &nbsp;|&nbsp; Bust ease: <b id="bust-ease">0</b> cm
    &nbsp;|&nbsp; Waist ease: <b id="waist-ease">0</b> cm
    &nbsp;|&nbsp; Corrections: <b id="n-corr">0</b>
  </div>
  <div style="display:flex; align-items:center; gap:10px; width:100%;">
    <button id="play-btn">&#9654; Play</button>
    <input type="range" id="slider" min="0" max="0" value="0" style="flex:1;">
  </div>
  <div id="stress-delta" style="font-size:12px; margin:2px 0;"></div>
  <div id="regional" style="font-size:11px; opacity:0.8; width:100%;"></div>
  <div id="issues"></div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
const DATA = __DATA__;
const M = DATA.mannequin;

const container = document.getElementById('container');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a2e);

const camera = new THREE.PerspectiveCamera(50, window.innerWidth/window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
container.appendChild(renderer.domElement);

const orbitControls = new THREE.OrbitControls(camera, renderer.domElement);
orbitControls.enableDamping = true;
orbitControls.dampingFactor = 0.08;

// Warm lighting for cloth appearance
scene.add(new THREE.AmbientLight(0xfff8f0, 0.55));
const dl1 = new THREE.DirectionalLight(0xfff8f0, 0.7);
dl1.position.set(50, 80, 60);
scene.add(dl1);
const dl2 = new THREE.DirectionalLight(0xfff0e8, 0.3);
dl2.position.set(-40, 30, -50);
scene.add(dl2);
scene.add(new THREE.HemisphereLight(0xfff8f0, 0x1a1a2e, 0.25));

const skinMat = new THREE.MeshPhongMaterial({
  color: 0xd4a574, shininess: 30, side: THREE.DoubleSide
});
const skinMatTransparent = new THREE.MeshPhongMaterial({
  color: 0xd4a574, transparent: true, opacity: 0.35, side: THREE.DoubleSide, depthWrite: false
});

// --- Torso body mesh ---
const bodyGeom = new THREE.BufferGeometry();
bodyGeom.setAttribute('position', new THREE.BufferAttribute(new Float32Array(DATA.body_vertices.flat()), 3));
const bIdx = []; DATA.body_faces.forEach(f => bIdx.push(f[0],f[1],f[2]));
bodyGeom.setIndex(bIdx);
bodyGeom.computeVertexNormals();
const bodyMesh = new THREE.Mesh(bodyGeom, skinMatTransparent);
scene.add(bodyMesh);

// --- Mannequin: Neck ---
const neckGeom = new THREE.CylinderGeometry(M.neck_radius, M.neck_radius * 1.1, M.neck_height, 16);
const neckMesh = new THREE.Mesh(neckGeom, skinMat);
neckMesh.position.set(0, M.torso_top_y + M.neck_height / 2, 0);
scene.add(neckMesh);

// --- Mannequin: Head ---
const headGeom = new THREE.SphereGeometry(M.head_radius, 20, 16);
const headMesh = new THREE.Mesh(headGeom, skinMat);
headMesh.position.set(0, M.torso_top_y + M.neck_height + M.head_radius * 0.85, 0);
headMesh.scale.set(1.0, 1.15, 0.95);
scene.add(headMesh);

// --- Mannequin: Arms ---
function addArm(side) {
  const armGeom = new THREE.CylinderGeometry(M.arm_radius * 0.85, M.arm_radius, M.arm_length, 12);
  const armMesh = new THREE.Mesh(armGeom, skinMat);
  const xSign = side === 'left' ? -1 : 1;
  armMesh.position.set(
    xSign * (M.shoulder_half_width + M.arm_length * 0.35),
    M.torso_top_y - M.arm_length * 0.35, 0
  );
  armMesh.rotation.z = xSign * 0.55;
  scene.add(armMesh);
  const capGeom = new THREE.SphereGeometry(M.arm_radius * 1.2, 12, 8);
  const capMesh = new THREE.Mesh(capGeom, skinMat);
  capMesh.position.set(xSign * M.shoulder_half_width, M.torso_top_y, 0);
  scene.add(capMesh);
}
addArm('left');
addArm('right');

// --- Garment mesh (cloth-colored with tension tint) ---
const garmentGeom = new THREE.BufferGeometry();
const initVerts = DATA.iterations[0].garment_vertices;
const gVerts = new Float32Array(initVerts.flat());
garmentGeom.setAttribute('position', new THREE.BufferAttribute(gVerts, 3));
const gIdx = []; DATA.garment_faces.forEach(f => gIdx.push(f[0],f[1],f[2]));
garmentGeom.setIndex(gIdx);

const nGV = initVerts.length;
const colorAttr = new Float32Array(nGV * 3);
garmentGeom.setAttribute('color', new THREE.BufferAttribute(colorAttr, 3));
garmentGeom.computeVertexNormals();

const garmentMesh = new THREE.Mesh(garmentGeom, new THREE.MeshPhongMaterial({
  vertexColors: true, side: THREE.DoubleSide, shininess: 8,
  transparent: true, opacity: 0.92
}));
scene.add(garmentMesh);

// Subtle garment wireframe
const gWire = new THREE.WireframeGeometry(garmentGeom);
const gWireMesh = new THREE.LineSegments(gWire, new THREE.LineBasicMaterial({
  color: 0xffffff, opacity: 0.04, transparent: true
}));
scene.add(gWireMesh);

// --- Cloth color: muslin base with warm tension tint ---
function stressToClothColor(stress, maxS, minS) {
  const range = Math.max(maxS - minS, 1);
  const t = Math.min(Math.max((stress - minS) / range, 0), 1.0);
  const mr = 0.96, mg = 0.94, mb = 0.88;
  if (t < 0.15) return [mr, mg, mb];
  else if (t < 0.4) {
    const u = (t - 0.15) / 0.25;
    return [mr, mg - u * 0.2, mb - u * 0.25];
  } else if (t < 0.7) {
    const u = (t - 0.4) / 0.3;
    return [0.96, 0.74 - u * 0.28, 0.63 - u * 0.35];
  } else {
    const u = (t - 0.7) / 0.3;
    return [0.96 - u * 0.18, 0.46 - u * 0.3, 0.28 - u * 0.12];
  }
}

const iterMinMax = DATA.iterations.map(it => {
  const vals = it.stresses.filter(s => s > 0);
  return { min: vals.length ? Math.min(...vals) : 0, max: vals.length ? Math.max(...vals) : 1 };
});
const globalMin = Math.min(...iterMinMax.map(m => m.min));
const globalMax = Math.max(...iterMinMax.map(m => m.max));

const initFrontDarts = DATA.iterations[0].front_darts;
const initBackDarts = DATA.iterations[0].back_darts;

// --- Seam lines ---
const SEAM_OFFSET = 0.15;
const seamLineObjects = [];

function createSeamLine(vertexIndices, color, dashed) {
  const positions = new Float32Array(vertexIndices.length * 3);
  const geom = new THREE.BufferGeometry();
  geom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  let mat;
  if (dashed) {
    mat = new THREE.LineDashedMaterial({ color: color, dashSize: 0.8, gapSize: 0.4, linewidth: 1 });
  } else {
    mat = new THREE.LineBasicMaterial({ color: color, linewidth: 2 });
  }
  const line = new THREE.Line(geom, mat);
  if (dashed) line.computeLineDistances();
  scene.add(line);
  return { line, geom, vertexIndices, dashed };
}

const SL = DATA.seam_lines;
if (SL) {
  if (SL.center_front) seamLineObjects.push(createSeamLine(SL.center_front, 0x1a237e, false));
  if (SL.center_back) seamLineObjects.push(createSeamLine(SL.center_back, 0x1a237e, false));
  if (SL.right_side) seamLineObjects.push(createSeamLine(SL.right_side, 0x1a237e, false));
  if (SL.left_side) seamLineObjects.push(createSeamLine(SL.left_side, 0x1a237e, false));
  if (SL.right_shoulder) seamLineObjects.push(createSeamLine(SL.right_shoulder, 0xbf360c, false));
  if (SL.left_shoulder) seamLineObjects.push(createSeamLine(SL.left_shoulder, 0xbf360c, false));
  if (SL.right_princess) seamLineObjects.push(createSeamLine(SL.right_princess, 0x4a148c, true));
  if (SL.left_princess) seamLineObjects.push(createSeamLine(SL.left_princess, 0x4a148c, true));
}

function updateSeamLines(garmentVerts) {
  seamLineObjects.forEach(obj => {
    const pos = obj.geom.attributes.position.array;
    for (let i = 0; i < obj.vertexIndices.length; i++) {
      const vi = obj.vertexIndices[i];
      if (vi < garmentVerts.length) {
        const pt = garmentVerts[vi];
        const rx = pt[0], rz = pt[2];
        const rn = Math.sqrt(rx*rx + rz*rz);
        const ox = rn > 0.001 ? rx/rn * SEAM_OFFSET : 0;
        const oz = rn > 0.001 ? rz/rn * SEAM_OFFSET : 0;
        pos[i*3] = pt[0] + ox; pos[i*3+1] = pt[1]; pos[i*3+2] = pt[2] + oz;
      }
    }
    obj.geom.attributes.position.needsUpdate = true;
    if (obj.dashed) obj.line.computeLineDistances();
  });
}

// --- Dart V-lines (updated per iteration) ---
const dartLineGroup = new THREE.Group();
scene.add(dartLineGroup);

function updateDartLines(dartLines3d) {
  // Remove old dart lines
  while (dartLineGroup.children.length > 0) {
    const child = dartLineGroup.children[0];
    if (child.geometry) child.geometry.dispose();
    if (child.material) child.material.dispose();
    dartLineGroup.remove(child);
  }
  if (!dartLines3d) return;

  const dartColor = 0xe65100;
  dartLines3d.forEach(d => {
    // V-line: leg1 -> apex -> leg2
    const positions = new Float32Array([
      d.leg1[0], d.leg1[1], d.leg1[2],
      d.apex[0], d.apex[1], d.apex[2],
      d.leg2[0], d.leg2[1], d.leg2[2]
    ]);
    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const mat = new THREE.LineBasicMaterial({ color: dartColor, linewidth: 2 });
    const line = new THREE.Line(geom, mat);
    dartLineGroup.add(line);

    // Semi-transparent filled triangle between the V legs
    const triGeom = new THREE.BufferGeometry();
    triGeom.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));
    triGeom.setIndex([0, 1, 2]);
    triGeom.computeVertexNormals();
    const triMat = new THREE.MeshBasicMaterial({
      color: dartColor, transparent: true, opacity: 0.25,
      side: THREE.DoubleSide, depthWrite: false
    });
    const tri = new THREE.Mesh(triGeom, triMat);
    dartLineGroup.add(tri);

    // Apex dot
    const dotGeom = new THREE.SphereGeometry(0.4, 8, 6);
    const dotMat = new THREE.MeshBasicMaterial({ color: dartColor });
    const dot = new THREE.Mesh(dotGeom, dotMat);
    dot.position.set(d.apex[0], d.apex[1], d.apex[2]);
    dartLineGroup.add(dot);
  });
}

function showIteration(idx) {
  const it = DATA.iterations[idx];
  if (!it) return;

  // Update garment vertex positions
  const positions = garmentGeom.attributes.position.array;
  for (let i = 0; i < it.garment_vertices.length; i++) {
    positions[i*3]   = it.garment_vertices[i][0];
    positions[i*3+1] = it.garment_vertices[i][1];
    positions[i*3+2] = it.garment_vertices[i][2];
  }
  garmentGeom.attributes.position.needsUpdate = true;
  garmentGeom.computeVertexNormals();
  garmentGeom.computeBoundingBox();
  garmentGeom.computeBoundingSphere();

  gWireMesh.geometry.dispose();
  gWireMesh.geometry = new THREE.WireframeGeometry(garmentGeom);

  // Update seam lines and dart lines
  updateSeamLines(it.garment_vertices);
  updateDartLines(it.dart_lines_3d);

  // Update cloth colors
  const colors = garmentGeom.attributes.color.array;
  for (let i = 0; i < it.stresses.length; i++) {
    const [r, g, b] = stressToClothColor(it.stresses[i], globalMax, globalMin);
    colors[i*3] = r; colors[i*3+1] = g; colors[i*3+2] = b;
  }
  garmentGeom.attributes.color.needsUpdate = true;

  document.getElementById('iter-num').textContent = it.iteration;
  document.getElementById('total-stress').textContent = it.total_stress;
  document.getElementById('bust-ease').textContent = it.bust_ease;
  document.getElementById('waist-ease').textContent = it.waist_ease;
  document.getElementById('n-corr').textContent = it.n_corrections;

  const issuesDiv = document.getElementById('issues');
  if (it.fit_issues.length === 0) {
    issuesDiv.innerHTML = '<span class="converged">✓ Converged — no fit issues</span>';
  } else {
    issuesDiv.innerHTML = it.fit_issues.map(fi =>
      '<div>⚠ ' + fi.region + ': ' + fi.type + ' (' + fi.stress + ' Pa, threshold ' + fi.threshold + ' Pa)</div>'
    ).join('');
  }

  const deltaDiv = document.getElementById('stress-delta');
  if (idx > 0) {
    const prev = DATA.iterations[idx-1];
    const delta = it.total_stress - prev.total_stress;
    const sign = delta <= 0 ? '↓' : '↑';
    const color = delta <= 0 ? '#69f0ae' : '#ff5252';
    deltaDiv.innerHTML = '<span style="color:'+color+'">'+sign+' '+Math.abs(delta).toFixed(1)+' Pa from previous</span>';
  } else {
    deltaDiv.innerHTML = '<span style="opacity:0.5">Initial sloper</span>';
  }

  const regDiv = document.getElementById('regional');
  if (it.regional_stresses) {
    const parts = Object.entries(it.regional_stresses).map(([k,v]) => {
      const pct = Math.min(v / Math.max(DATA.max_stress,1) * 100, 100);
      const c = pct < 33 ? '#69f0ae' : pct < 66 ? '#ffeb3b' : '#ff5252';
      return '<span style="color:'+c+'">'+k+': '+v+'Pa</span>';
    });
    regDiv.innerHTML = parts.join(' · ');
  }

  // Dart info panel
  const dartDiv = document.getElementById('dart-info');
  let h = '';
  it.front_darts.forEach((d, i) => {
    const label = i === 0 ? 'Front bust dart' : 'Front waist dart';
    const init = initFrontDarts[i] ? initFrontDarts[i].angle : d.angle;
    const delta = d.angle - init;
    const ds = delta > 0.01 ? '<span class="ease-change">+' + delta.toFixed(1) + '°</span>' : '';
    const bw = Math.min(d.angle / 40 * 120, 120);
    h += '<div class="dart-row"><span class="dart-label">'+label+'</span>' +
      '<span class="dart-val">'+d.angle.toFixed(1)+'° × '+d.length.toFixed(1)+'cm'+ds+'</span></div>' +
      '<div class="dart-bar-bg"><div class="dart-bar" style="width:'+bw+'px"></div></div>';
  });
  it.back_darts.forEach((d, i) => {
    const init = initBackDarts[i] ? initBackDarts[i].angle : d.angle;
    const delta = d.angle - init;
    const ds = delta > 0.01 ? '<span class="ease-change">+' + delta.toFixed(1) + '°</span>' : '';
    const bw = Math.min(d.angle / 40 * 120, 120);
    h += '<div class="dart-row"><span class="dart-label">Back dart '+(i+1)+'</span>' +
      '<span class="dart-val">'+d.angle.toFixed(1)+'° × '+d.length.toFixed(1)+'cm'+ds+'</span></div>' +
      '<div class="dart-bar-bg"><div class="dart-bar" style="width:'+bw+'px"></div></div>';
  });
  const beDelta = it.bust_ease - DATA.iterations[0].bust_ease;
  const weDelta = it.waist_ease - DATA.iterations[0].waist_ease;
  h += '<div style="margin-top:6px;border-top:1px solid #333;padding-top:6px;">';
  h += '<div class="dart-row"><span class="dart-label">Bust ease</span><span class="dart-val">'+
    it.bust_ease.toFixed(2)+' cm'+(beDelta>0.01?'<span class="ease-change">+'+beDelta.toFixed(2)+'</span>':'')+
    '</span></div>';
  h += '<div class="dart-row"><span class="dart-label">Waist ease</span><span class="dart-val">'+
    it.waist_ease.toFixed(2)+' cm'+(weDelta>0.01?'<span class="ease-change">+'+weDelta.toFixed(2)+'</span>':'')+
    '</span></div></div>';
  dartDiv.innerHTML = h;
}

// Slider + play
const slider = document.getElementById('slider');
slider.max = DATA.iterations.length - 1;
document.getElementById('iter-max').textContent = DATA.iterations.length - 1;
document.getElementById('max-label').textContent = Math.round(globalMax) + ' Pa';
slider.addEventListener('input', () => showIteration(parseInt(slider.value)));

let playInterval = null;
const playBtn = document.getElementById('play-btn');
playBtn.addEventListener('click', () => {
  if (playInterval) { clearInterval(playInterval); playInterval = null; playBtn.textContent = '\u25b6 Play'; return; }
  playBtn.textContent = '\u23f8 Pause';
  if (+slider.value >= +slider.max) slider.value = 0;
  playInterval = setInterval(() => {
    slider.value = +slider.value + 1;
    showIteration(+slider.value);
    if (+slider.value >= +slider.max) { clearInterval(playInterval); playInterval = null; playBtn.textContent = '\u25b6 Play'; }
  }, 600);
});

// Camera
bodyGeom.computeBoundingBox();
const box = bodyGeom.boundingBox;
const center = new THREE.Vector3(); box.getCenter(center);
const sz = new THREE.Vector3(); box.getSize(sz);
center.y += M.neck_height + M.head_radius;
camera.position.set(center.x + sz.x * 2.0, center.y + sz.y * 0.1, center.z + sz.z * 3.0);
orbitControls.target.copy(center);
orbitControls.update();

showIteration(0);

function animate() {
  requestAnimationFrame(animate);
  orbitControls.update();
  renderer.render(scene, camera);
}
animate();

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowRight') { slider.value = Math.min(+slider.value+1, +slider.max); showIteration(+slider.value); }
  if (e.key === 'ArrowLeft') { slider.value = Math.max(+slider.value-1, 0); showIteration(+slider.value); }
});
</script>
</body>
</html>"""
