"""HTML/Three.js visualizer for the agentic pattern engine.

Generates a self-contained HTML file that shows:
- The 3D body model (semi-transparent)
- The garment mesh draped on the body, colored by per-vertex tension
- A slider to scrub through self-correction iterations

Open the resulting HTML in any modern browser.
"""

from __future__ import annotations

import json

import numpy as np

from agentic_pattern_engine.models import (
    AuditTrail,
    BodyModel,
    BodiceSloper,
    TensionThresholds,
)
from agentic_pattern_engine.simulation_engine import MassSpringSimulationEngine


def generate_visualization(
    body_model: BodyModel,
    audit_trail: AuditTrail,
    thresholds: TensionThresholds | None = None,
) -> str:
    """Generate a self-contained HTML visualization.

    Re-simulates each iteration's sloper against the body model to
    produce garment meshes and tension heatmaps.
    """
    sim = MassSpringSimulationEngine()
    thresholds = thresholds or TensionThresholds()

    # Collect body mesh data
    body_verts = body_model.vertices.tolist()
    body_faces = body_model.faces.tolist()

    # Collect per-iteration garment data
    iterations_data: list[dict] = []

    for entry in audit_trail.entries:
        sloper = entry.sloper

        # Re-simulate to get garment mesh positions and stresses
        sim_result = sim.simulate(sloper, body_model)
        garment_verts = sim._map_pattern_to_body(sloper, body_model).tolist()
        stresses = sim_result.tension_map.vertex_stresses.tolist()

        # Build simple triangle fan for garment visualization
        n_front = len(sloper.front_bodice.outline) - 1  # skip closing pt
        n_back = len(sloper.back_bodice.outline) - 1
        n_front_darts = len(sloper.front_bodice.darts)
        n_front_notches = len(sloper.front_bodice.notch_marks)
        n_back_darts = len(sloper.back_bodice.darts)
        n_back_notches = len(sloper.back_bodice.notch_marks)

        total_front = n_front + n_front_darts + n_front_notches
        total_back = n_back + n_back_darts + n_back_notches

        garment_faces = []
        # Fan triangulate front piece (first total_front vertices)
        for i in range(1, total_front - 1):
            garment_faces.append([0, i, i + 1])
        # Fan triangulate back piece
        offset = total_front
        for i in range(1, total_back - 1):
            garment_faces.append([offset, offset + i, offset + i + 1])

        # Fit issues summary
        issues = []
        for fi in entry.fit_issues:
            issues.append({
                "region": fi.region.value,
                "type": fi.issue_type.value,
                "stress": round(fi.measured_stress, 1),
                "threshold": round(fi.threshold, 1),
            })

        iterations_data.append({
            "iteration": entry.iteration,
            "garment_vertices": garment_verts,
            "garment_faces": garment_faces,
            "stresses": stresses,
            "total_stress": round(entry.total_stress_magnitude, 1),
            "fit_issues": issues,
            "bust_ease": round(sloper.bust_ease, 2),
            "waist_ease": round(sloper.waist_ease, 2),
        })

    data = {
        "body_vertices": body_verts,
        "body_faces": body_faces,
        "iterations": iterations_data,
        "max_stress": round(max(
            max(it["stresses"]) if it["stresses"] else 0
            for it in iterations_data
        ), 1),
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
    background: rgba(0,0,0,0.8); padding: 16px 24px; border-radius: 12px;
    display: flex; flex-direction: column; align-items: center; gap: 8px;
    min-width: 500px;
  }
  #slider { width: 100%; cursor: pointer; }
  .info { font-size: 13px; opacity: 0.9; }
  .info b { color: #4fc3f7; }
  #issues { font-size: 12px; color: #ffab91; max-height: 80px; overflow-y: auto; width: 100%; }
  #legend {
    position: absolute; top: 20px; right: 20px;
    background: rgba(0,0,0,0.8); padding: 12px 16px; border-radius: 8px;
    font-size: 12px;
  }
  .legend-bar {
    width: 150px; height: 16px; border-radius: 4px;
    background: linear-gradient(to right, #00c853, #ffeb3b, #ff1744);
    margin: 4px 0;
  }
  .legend-labels { display: flex; justify-content: space-between; font-size: 11px; }
  h3 { font-size: 14px; margin-bottom: 4px; color: #4fc3f7; }
</style>
</head>
<body>
<div id="container"></div>
<div id="legend">
  <h3>Tension Heatmap</h3>
  <div class="legend-bar"></div>
  <div class="legend-labels"><span>0 Pa</span><span id="max-stress-label">500 Pa</span></div>
</div>
<div id="controls">
  <div class="info">
    Iteration: <b id="iter-num">0</b> / <b id="iter-max">0</b>
    &nbsp;|&nbsp; Total stress: <b id="total-stress">0</b> Pa
    &nbsp;|&nbsp; Bust ease: <b id="bust-ease">0</b> cm
    &nbsp;|&nbsp; Waist ease: <b id="waist-ease">0</b> cm
  </div>
  <input type="range" id="slider" min="0" max="0" value="0">
  <div id="issues"></div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
const DATA = __DATA__;

// Scene setup
const container = document.getElementById('container');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a2e);
const camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
container.appendChild(renderer.domElement);

const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

// Lighting
scene.add(new THREE.AmbientLight(0xffffff, 0.5));
const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
dirLight.position.set(50, 80, 50);
scene.add(dirLight);
const dirLight2 = new THREE.DirectionalLight(0xffffff, 0.3);
dirLight2.position.set(-50, 40, -50);
scene.add(dirLight2);

// Body mesh (semi-transparent)
const bodyGeom = new THREE.BufferGeometry();
const bv = new Float32Array(DATA.body_vertices.flat());
bodyGeom.setAttribute('position', new THREE.BufferAttribute(bv, 3));
const bi = [];
DATA.body_faces.forEach(f => bi.push(f[0], f[1], f[2]));
bodyGeom.setIndex(bi);
bodyGeom.computeVertexNormals();
const bodyMat = new THREE.MeshPhongMaterial({
  color: 0x90a4ae, transparent: true, opacity: 0.35, side: THREE.DoubleSide
});
const bodyMesh = new THREE.Mesh(bodyGeom, bodyMat);
scene.add(bodyMesh);

// Wireframe for body
const wireGeo = new THREE.WireframeGeometry(bodyGeom);
const wireMat = new THREE.LineBasicMaterial({ color: 0x546e7a, opacity: 0.3, transparent: true });
scene.add(new THREE.LineSegments(wireGeo, wireMat));

// Garment mesh (will be updated per iteration)
let garmentMesh = null;

function stressToColor(stress, maxStress) {
  const t = Math.min(stress / Math.max(maxStress, 1), 1.0);
  // green -> yellow -> red
  const r = t < 0.5 ? t * 2 : 1.0;
  const g = t < 0.5 ? 1.0 : 1.0 - (t - 0.5) * 2;
  const b = 0;
  return [r, g, b];
}

function showIteration(idx) {
  const it = DATA.iterations[idx];
  if (!it) return;

  // Remove old garment
  if (garmentMesh) { scene.remove(garmentMesh); garmentMesh.geometry.dispose(); }

  const geom = new THREE.BufferGeometry();
  const verts = new Float32Array(it.garment_vertices.flat());
  geom.setAttribute('position', new THREE.BufferAttribute(verts, 3));

  // Vertex colors from stress
  const colors = new Float32Array(it.garment_vertices.length * 3);
  const maxS = DATA.max_stress || 500;
  for (let i = 0; i < it.stresses.length; i++) {
    const [r, g, b] = stressToColor(it.stresses[i], maxS);
    colors[i*3] = r; colors[i*3+1] = g; colors[i*3+2] = b;
  }
  geom.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const faces = [];
  it.garment_faces.forEach(f => faces.push(f[0], f[1], f[2]));
  geom.setIndex(faces);
  geom.computeVertexNormals();

  const mat = new THREE.MeshPhongMaterial({
    vertexColors: true, side: THREE.DoubleSide, shininess: 30,
    transparent: true, opacity: 0.85,
  });
  garmentMesh = new THREE.Mesh(geom, mat);
  scene.add(garmentMesh);

  // Update UI
  document.getElementById('iter-num').textContent = it.iteration;
  document.getElementById('total-stress').textContent = it.total_stress;
  document.getElementById('bust-ease').textContent = it.bust_ease;
  document.getElementById('waist-ease').textContent = it.waist_ease;

  const issuesDiv = document.getElementById('issues');
  if (it.fit_issues.length === 0) {
    issuesDiv.innerHTML = '<span style="color:#69f0ae">✓ Converged — no fit issues</span>';
  } else {
    issuesDiv.innerHTML = it.fit_issues.map(fi =>
      `<div>⚠ ${fi.region}: ${fi.type} (${fi.stress} Pa, threshold ${fi.threshold} Pa)</div>`
    ).join('');
  }
}

// Slider
const slider = document.getElementById('slider');
slider.max = DATA.iterations.length - 1;
document.getElementById('iter-max').textContent = DATA.iterations.length - 1;
document.getElementById('max-stress-label').textContent = (DATA.max_stress || 500) + ' Pa';
slider.addEventListener('input', () => showIteration(parseInt(slider.value)));

// Camera position
bodyGeom.computeBoundingBox();
const box = bodyGeom.boundingBox;
const center = new THREE.Vector3();
box.getCenter(center);
const size = new THREE.Vector3();
box.getSize(size);
camera.position.set(center.x + size.x * 2, center.y + size.y * 0.5, center.z + size.z * 3);
controls.target.copy(center);
controls.update();

// Initial render
showIteration(0);

// Animation loop
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();

// Resize
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// Keyboard: left/right arrows to scrub
document.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowRight') { slider.value = Math.min(+slider.value + 1, +slider.max); showIteration(+slider.value); }
  if (e.key === 'ArrowLeft') { slider.value = Math.max(+slider.value - 1, 0); showIteration(+slider.value); }
});
</script>
</body>
</html>"""
