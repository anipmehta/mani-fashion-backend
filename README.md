# MANI Agentic Pattern Engine

A headless, deterministic bodice sloper generator with an agentic self-correction loop. Takes 5 body measurements and produces a production-ready bodice pattern (front + back) with darts, seam lines, and construction marks — automatically corrected for fit through iterative tension simulation.

## What It Does

```
Measurements → Sloper Draft → Simulate → Detect Issues → Correct → Repeat → Export
     (5 inputs)    (Parsons)    (stress)    (threshold)   (darts/ease)         (DXF/PDF/OBJ/HTML)
```

1. **Generates a bodice sloper** from chest, waist, hip, shoulder width, and torso length using the Parsons flat-pattern method
2. **Simulates cloth tension** — computes per-region stress (bust, waist, shoulder, armhole, side seam, CF, CB) based on how the flat pattern conforms to the 3D body
3. **Detects fit issues** — classifies regions exceeding tension thresholds
4. **Self-corrects** — widens dart angles, adjusts ease, redistributes fabric until all regions converge
5. **Exports** — DXF (CAD), PDF (printable), OBJ (3D), and an interactive Three.js HTML visualization

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Run with direct measurements (cm)
python -m agentic_pattern_engine.cli \
    --chest 88 --waist 70 --hip 94 \
    --shoulder-width 38 --torso-length 46 \
    --output-dir ./output --dump-iterations

# Run with tight thresholds (forces more correction iterations)
python -m agentic_pattern_engine.cli \
    --chest 100 --waist 68 --hip 104 \
    --shoulder-width 36 --torso-length 44 \
    --tight-thresholds --verbose \
    --output-dir ./output --dump-iterations
```

## Output Files

| File | Description |
|------|-------------|
| `pattern.dxf` | DXF pattern file — open in any CAD software (Inkscape, AutoCAD, Lectra, Gerber) |
| `pattern.pdf` | Printable pattern at scale |
| `body_model.obj` | 3D torso mesh (OBJ) |
| `pattern.obj` | 3D pattern pieces (OBJ) |
| `visualization.html` | Interactive 3D visualization — open in any browser |
| `iterations/` | Per-iteration OBJ snapshots (with `--dump-iterations`) |

## 3D Visualization

Open `visualization.html` in a browser to see:
- Mannequin body form with head, neck, and arm stubs
- Cloth-colored garment (muslin base with warm tension tint)
- Seam lines (CF, CB, side, shoulder), princess lines, dart V-lines
- Iteration slider showing the self-correction loop in action
- Per-region stress values, dart angles, and ease changes per iteration

## Convergence Behavior

Tested across 14 body profiles (petite through plus-size, 60cm–170cm chest):

| Profile | Chest/Waist | Default | Tight |
|---------|-------------|---------|-------|
| Petite (XS) | 76/60 | 5 iter | 7 iter |
| Average (M) | 88/70 | 7 iter | 8 iter |
| Athletic (M) | 92/72 | 7 iter | 8 iter |
| Curvy (L) | 96/74 | 6 iter | 7 iter |
| Plus (XL) | 108/86 | 5 iter | 9 iter |
| Plus (2XL) | 118/96 | 4 iter | 10 iter |
| High differential | 100/68 | 5 iter | 6 iter |
| Low differential | 85/80 | 1 iter | 6 iter |

All profiles converge. No hardcoded hacks for specific body types.

## Architecture

```
agentic_pattern_engine/
├── models.py              # All data models (measurements, pattern pieces, darts, tension)
├── sloper_generator.py    # Parsons-method bodice drafting (front + back)
├── body_model_builder.py  # Parametric 3D torso mesh (elliptical cross-sections)
├── simulation_engine.py   # Mass-spring stress computation with 3D shaping model
├── fit_detector.py        # Threshold-based fit issue classification
├── geometry_corrector.py  # Dart angle/length/ease correction planning
├── agent_orchestrator.py  # Self-correction loop (sense → plan → act → repeat)
├── dxf_exporter.py        # DXF pattern export
├── pdf_exporter.py        # PDF pattern export
├── html_visualizer.py     # Three.js 3D visualization
├── audit_trail.py         # Per-iteration recording
└── cli.py                 # Command-line interface
```

## How the Self-Correction Loop Works

The agent orchestrator runs a sense-plan-act loop:

1. **Generate** initial sloper from measurements (Parsons method, 5cm bust ease, 3cm waist ease)
2. **Simulate** cloth tension — computes stress per region based on garment-vs-body fit and 3D shaping difficulty
3. **Detect** fit issues — any region exceeding its threshold is flagged
4. **Plan corrections** — prioritizes excess tension, then pulling, then insufficient tension. Widens dart angles, redistributes ease
5. **Apply** corrections to the sloper
6. **Repeat** from step 2 until no issues remain (converged), stress stops decreasing (stalled), or iteration limit reached

Safety mechanisms:
- **Oscillation detection**: if the same regions keep flipping, dampening factor reduces correction magnitude
- **Stall detection**: if total stress doesn't decrease for N iterations, stops early
- **Max ease tolerance**: prevents corrections from adding excessive ease

## Tests

```bash
pytest tests/ -q
# 28 passed
```

## CLI Options

```
--chest, --waist, --hip, --shoulder-width, --torso-length   Body measurements (cm)
--profile PATH          JSON file with measurements
--output-dir PATH       Output directory (default: ./output)
--dump-iterations       Export OBJ for every iteration
--tight-thresholds      Use tight tension thresholds (more iterations)
--verbose               Show per-iteration audit trail
--iteration-limit N     Max iterations (default: 20)
--stall-threshold N     Iterations to check for stall (default: 5)
--max-ease-tolerance F  Max ease change per correction (default: 2.0 cm)
```

## Known Limitations

- **Straight-line pattern edges**: armhole, neckline, and side seams use straight segments between construction points (real patterns use French curves)
- **Dart marks only**: DXF marks dart apex + angle but doesn't slash the wedge into the outline
- **No seam allowance outlines**: 1.5cm seam allowance is stored but not drawn as offset cutting lines
- **5 measurements**: more measurements (bust point height, back neck to waist, armhole depth) would improve accuracy
- **Analytical simulation**: stress model uses circumference ratios + shaping heuristic, not FEM cloth physics
- **Bodice only**: front and back bodice block — no sleeves, skirt, collar

## License

See [LICENSE](LICENSE).
