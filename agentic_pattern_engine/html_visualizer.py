"""HTML/Three.js visualizer for the agentic pattern engine.

Generates a self-contained HTML file that shows:
- The 3D body model (semi-transparent)
- A garment shell mesh draped on the body, colored by per-region tension
- A slider to scrub through self-correction iterations

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


# Number of points around each garment cross-section ring
_RING_PTS = 20
# Garment offset from body surface (cm)
_GARMENT_OFFSET = 0.8


def _build_garment_shell(body_model: BodyModel) -> tuple[list, list]:
    """Build a garment shell mesh that wraps around the body.

    Creates a cylindrical grid by offsetting each body cross-section
    outward, producing a continuous surface that looks like draped fabric.

    Returns (vertices, faces) where vertices is list of [x,y,z] and
    faces is list of [i,j,k] triangle indices.
    """
    bv = body_model.vertices
    n_body = len(bv)

    # The body has 4 cross-section rings of 20 points each (80 total).
    # Detect ring size from the body mesh structure.
    # Points at the same y-level form a ring.
    y_values = sorted(set(round(float(v[1]), 4) for v in bv))
    n_rings = len(y_values)
    pts_per_ring = n_body // n_rings if n_rings > 0 else 20

    garment_verts: list[list[float]] = []
    for vi in range(n_body):
        pt = bv[vi].copy()
        # Offset outward in the XZ plane (radial direction)
        radial = np.array([pt[0], 0.0, pt[2]])
        norm = np.linalg.norm(radial)
        if norm > 1e-6:
            pt += (radial / norm) * _GARMENT_OFFSET
        garment_verts.append(pt.tolist())

    # Build quad faces between adjacent rings, split into triangles
    garment_faces: list[list[int]] = []
    for ring in range(n_rings - 1):
        for i in range(pts_per_ring):
            # Current ring vertex indices
            a = ring * pts_per_ring + i
            b = ring * pts_per_ring + (i + 1) % pts_per_ring
            # Next ring vertex indices
            c = (ring + 1) * pts_per_ring + i
            d = (ring + 1) * pts_per_ring + (i + 1) % pts_per_ring
            garment_faces.append([a, c, b])
            garment_faces.append([b, c, d])

    return garment_verts, garment_faces


def _vertex_region_stress(
    body_model: BodyModel,
    regional_stresses: dict[str, float],
) -> list[float]:
    """Map regional stress values to per-vertex stress for the garment shell.

    Each vertex gets the stress of its nearest body region.
    """
    bv = body_model.vertices
    n = len(bv)
    fr = body_model.fit_regions

    # Build vertex -> region mapping
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


def generate_visualization(
    body_model: BodyModel,
    audit_trail: AuditTrail,
    thresholds: TensionThresholds | None = None,
) -> str:
    """Generate a self-contained HTML visualization."""
    sim = MassSpringSimulationEngine()
    thresholds = thresholds or TensionThresholds()

    # Body mesh data
    body_verts = body_model.vertices.tolist()
    body_faces = body_model.faces.tolist()

    # Build garment shell (same topology for all iterations, just colors change)
    garment_verts, garment_faces = _build_garment_shell(body_model)

    # Collect per-iteration stress data
    iterations_data: list[dict] = []
    max_stress = 0.0

    for entry in audit_trail.entries:
        sloper = entry.sloper

        # Get regional stresses from simulation
        regional = sim._compute_regional_stresses(sloper, body_model.profile)

        # Map to per-vertex stress
        vertex_stresses = _vertex_region_stress(body_model, regional)
        local_max = max(vertex_stresses) if vertex_stresses else 0.0
        if local_max > max_stress:
            max_stress = local_max

        # Fit issues summary
        issues = []
        for fi in entry.fit_issues:
            issues.append({
                "region": fi.region.value,
                "type": fi.issue_type.value,
                "stress": round(fi.measured_stress, 1),
                "threshold": round(fi.threshold, 1),
            })

        # Use re-computed stress total (not audit trail's 0.0 for iter 0)
        computed_total = sum(
            max(0.0, regional.get(fi_region, 0.0) - getattr(thresholds, fi_region, 500.0))
            for fi_region in ("bust", "waist", "shoulder", "armhole",
                              "side_seam", "center_front", "center_back")
        )
        display_total = round(computed_total, 1) if entry.iteration == 0 else round(entry.total_stress_magnitude, 1)

        iterations_data.append({
            "iteration": entry.iteration,
            "stresses": [round(s, 2) for s in vertex_stresses],
            "total_stress": display_total,
            "regional_stresses": {k: round(v, 1) for k, v in regional.items()},
            "fit_issues": issues,
            "bust_ease": round(sloper.bust_ease, 2),
            "waist_ease": round(sloper.waist_ease, 2),
            "n_corrections": len(entry.corrections_applied),
        })

    data = {
        "body_vertices": body_verts,
        "body_faces": body_faces,
        "garment_vertices": garment_verts,
        "garment_faces": garment_faces,
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
    min-width: 560px; backdrop-filter: blur(8px);
  }
  #slider { width: 100%; cursor: pointer; accent-color: #4fc3f7; }
  .info { font-size: 13px; opacity: 0.9; }
  .info b { color: #4fc3f7; }
  #issues { font-size: 12px; color: #ffab91; max-height: 80px; overflow-y: auto; width: 100%; }
  #legend {
    position: absolute; top: 20px; right: 20px;
    background: rgba(0,0,0,0.85); padding: 12px 16px; border-radius: 8px;
    font-size: 12px; backdrop-filter: blur(8px);
  }
  .legend-bar {
    width: 150px; height: 16px; border-radius: 4px;
    background: linear-gradient(to right, #00c853, #ffeb3b, #ff1744);
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
</style>
</head>
<body>
<div id="container"></div>
<div id="title">
  <h2>MANI Agentic Pattern Engine</h2>
  <p>Bodice drape simulation with tension heatmap</p>
  <p style="margin-top:4px">Drag to rotate · Scroll to zoom · Arrow keys to scrub</p>
</div>
<div id="legend">
  <h3>Tension Heatmap</h3>
  <div class="legend-bar"></div>
  <div class="legend-labels"><span>0 Pa (good fit)</span><span id="max-label">500 Pa</span></div>
  <div style="margin-top:8px; font-size:11px; opacity:0.7">
    <div>🟢 Green = within threshold</div>
    <div>🟡 Yellow = approaching limit</div>
    <div>🔴 Red = excess tension</div>
  </div>
</div>
<div id="controls">
  <div class="info">
    Iteration: <b id="iter-num">0</b> / <b id="iter-max">0</b>
    &nbsp;|&nbsp; Total stress: <b id="total-stress">0</b> Pa
    &nbsp;|&nbsp; Bust ease: <b id="bust-ease">0</b> cm
    &nbsp;|&nbsp; Waist ease: <b id="waist-ease">0</b> cm
    &nbsp;|&nbsp; Corrections: <b id="n-corr">0</b>
  </div>
  <input type="range" id="slider" min="0" max="0" value="0">
  <div id="stress-delta" style="font-size:12px; margin:2px 0;"></div>
  <div id="regional" style="font-size:11px; opacity:0.8; width:100%;"></div>
  <div id="issues"></div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
const DATA = __DATA__;

const container = document.getElementById('container');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a2e);

const camera = new THREE.PerspectiveCamera(50, window.innerWidth/window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
container.appendChild(renderer.domElement);

const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;

// Lighting
scene.add(new THREE.AmbientLight(0xffffff, 0.4));
const d1 = new THREE.DirectionalLight(0xffffff, 0.7);
d1.position.set(50, 80, 60);
scene.add(d1);
const d2 = new THREE.DirectionalLight(0xffffff, 0.3);
d2.position.set(-40, 30, -50);
scene.add(d2);
scene.add(new THREE.HemisphereLight(0x4fc3f7, 0x1a1a2e, 0.2));

// --- Body mesh ---
const bodyGeom = new THREE.BufferGeometry();
bodyGeom.setAttribute('position', new THREE.BufferAttribute(new Float32Array(DATA.body_vertices.flat()), 3));
const bIdx = []; DATA.body_faces.forEach(f => bIdx.push(f[0],f[1],f[2]));
bodyGeom.setIndex(bIdx);
bodyGeom.computeVertexNormals();
const bodyMesh = new THREE.Mesh(bodyGeom, new THREE.MeshPhongMaterial({
  color: 0x78909c, transparent: true, opacity: 0.3, side: THREE.DoubleSide, depthWrite: false
}));
scene.add(bodyMesh);

// Body wireframe
const wireGeo = new THREE.WireframeGeometry(bodyGeom);
scene.add(new THREE.LineSegments(wireGeo, new THREE.LineBasicMaterial({
  color: 0x546e7a, opacity: 0.15, transparent: true
})));

// --- Garment mesh ---
const garmentGeom = new THREE.BufferGeometry();
const gVerts = new Float32Array(DATA.garment_vertices.flat());
garmentGeom.setAttribute('position', new THREE.BufferAttribute(gVerts, 3));
const gIdx = []; DATA.garment_faces.forEach(f => gIdx.push(f[0],f[1],f[2]));
garmentGeom.setIndex(gIdx);

// Vertex colors (will be updated per iteration)
const nGarmentVerts = DATA.garment_vertices.length;
const colorAttr = new Float32Array(nGarmentVerts * 3);
garmentGeom.setAttribute('color', new THREE.BufferAttribute(colorAttr, 3));
garmentGeom.computeVertexNormals();

const garmentMesh = new THREE.Mesh(garmentGeom, new THREE.MeshPhongMaterial({
  vertexColors: true, side: THREE.DoubleSide, shininess: 20,
  transparent: true, opacity: 0.85
}));
scene.add(garmentMesh);

// Garment wireframe (subtle)
const gWire = new THREE.WireframeGeometry(garmentGeom);
const gWireMesh = new THREE.LineSegments(gWire, new THREE.LineBasicMaterial({
  color: 0xffffff, opacity: 0.08, transparent: true
}));
scene.add(gWireMesh);

function stressToColor(stress, maxS, minS) {
  // Normalize to [0,1] using the actual stress range for better contrast
  const range = Math.max(maxS - minS, 1);
  const t = Math.min(Math.max((stress - minS) / range, 0), 1.0);
  let r, g, b;
  if (t < 0.5) {
    r = t * 2; g = 1.0; b = 0;
  } else {
    r = 1.0; g = 1.0 - (t - 0.5) * 2; b = 0;
  }
  return [r, g, b];
}

// Precompute per-iteration min/max stress for better color contrast
const iterMinMax = DATA.iterations.map(it => {
  const vals = it.stresses.filter(s => s > 0);
  return {
    min: vals.length ? Math.min(...vals) : 0,
    max: vals.length ? Math.max(...vals) : 1
  };
});
// Global min/max across all iterations
const globalMin = Math.min(...iterMinMax.map(m => m.min));
const globalMax = Math.max(...iterMinMax.map(m => m.max));

function showIteration(idx) {
  const it = DATA.iterations[idx];
  if (!it) return;

  const colors = garmentGeom.attributes.color.array;
  for (let i = 0; i < it.stresses.length; i++) {
    const [r, g, b] = stressToColor(it.stresses[i], globalMax, globalMin);
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

  // Stress delta from previous iteration
  const deltaDiv = document.getElementById('stress-delta');
  if (idx > 0) {
    const prev = DATA.iterations[idx-1];
    const delta = it.total_stress - prev.total_stress;
    const sign = delta <= 0 ? '↓' : '↑';
    const color = delta <= 0 ? '#69f0ae' : '#ff5252';
    deltaDiv.innerHTML = '<span style="color:'+color+'">'+sign+' '+Math.abs(delta).toFixed(1)+' Pa from previous iteration</span>';
  } else {
    deltaDiv.innerHTML = '<span style="opacity:0.5">Initial sloper (pre-simulation baseline)</span>';
  }

  // Regional stress breakdown
  const regDiv = document.getElementById('regional');
  if (it.regional_stresses) {
    const parts = Object.entries(it.regional_stresses).map(([k,v]) => {
      const pct = Math.min(v / Math.max(DATA.max_stress,1) * 100, 100);
      const c = pct < 33 ? '#69f0ae' : pct < 66 ? '#ffeb3b' : '#ff5252';
      return '<span style="color:'+c+'">'+k+': '+v+'Pa</span>';
    });
    regDiv.innerHTML = parts.join(' · ');
  }
}

// Slider
const slider = document.getElementById('slider');
slider.max = DATA.iterations.length - 1;
document.getElementById('iter-max').textContent = DATA.iterations.length - 1;
document.getElementById('max-label').textContent = (DATA.max_stress || 500) + ' Pa';
document.getElementById('max-label').textContent = Math.round(globalMax) + ' Pa';
slider.addEventListener('input', () => showIteration(parseInt(slider.value)));

// Camera
bodyGeom.computeBoundingBox();
const box = bodyGeom.boundingBox;
const center = new THREE.Vector3(); box.getCenter(center);
const size = new THREE.Vector3(); box.getSize(size);
camera.position.set(center.x + size.x * 1.5, center.y + size.y * 0.3, center.z + size.z * 2.5);
controls.target.copy(center);
controls.update();

showIteration(0);

function animate() {
  requestAnimationFrame(animate);
  controls.update();
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
