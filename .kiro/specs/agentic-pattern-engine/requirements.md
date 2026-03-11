# Requirements Document

## Introduction

This document defines the requirements for the Agentic Pattern Engine POC — the core differentiating technology within the MANI platform. Current generative AI suffers from "Geometry Blindness": it can render a beautiful image of a dress (pixels) but cannot generate a sewable 3D pattern (topology). The Agentic Pattern Engine solves this by using an autonomous AI agent as a "Digital Design Engineer" that can generate bodice slopers from body measurements, simulate their physical behavior on a digital twin, detect fit problems (excess tension, pulling, gapping), and autonomously recalculate dart geometry until the fit is mathematically guaranteed — a "Validation-before-Cutting" approach that ensures no fabric is wasted on a garment that won't fit.

Unlike a chatbot, the agent operates in a closed self-correction loop: generate → simulate → detect → recalculate → re-simulate, iterating until all fit criteria pass or a maximum iteration limit is reached. This POC validates the core agentic loop on a single garment type (bodice/top block only — no trousers, no sleeves) before extending to other block types. The architecture is designed to support additional garment types in the future.

### POC Scope

The POC pipeline consists of six stages:

1. **Measurements → SMPL Digital Twin**: Customer measurements are converted into a 3D body model using SMPL/SMPL-X via FlexiSMPL.
2. **Parametric Bodice Sloper Generation**: A bodice sloper is generated using PyGarment (GarmentCode) with Parsons-method drafting formulas.
3. **Cloth Simulation on Digital Twin**: The sloper is draped on the digital twin using GPU-accelerated mass-spring cloth simulation (NVIDIA Warp or Taichi), running headless.
4. **Agentic Self-Correction Loop**: The agent detects tension, adjusts darts/ease, re-simulates, and iterates until convergence.
5. **Production-Ready DXF/PDF Export**: The corrected pattern is exported as DXF (via ezdxf) and PDF (via reportlab) for the tailor partner.
6. **Full Audit Trail**: Every iteration is recorded for debugging and analysis.

### Explicitly Out of Scope

- No UI/frontend (headless CLI/API only)
- No ML-based fit prediction
- Bodice/top block only (no trousers, no sleeves)
- No real-time visual feedback

### Tech Stack

- **PyGarment** (GarmentCode) for parametric sewing pattern DSL
- **SMPL/SMPL-X** + **FlexiSMPL** for measurements → 3D body mesh
- **NVIDIA Warp** or **Taichi** for GPU cloth simulation (mass-spring, headless, differentiable)
- **ezdxf** for DXF export
- **reportlab** for PDF export
- **trimesh** for mesh I/O
- **pytest** + **hypothesis** for property-based testing

This spec builds on the existing MANI platform spec (`.kiro/specs/custom-fashion-platform/`), which covers measurement input, basic Parsons-method sloper generation, tailor delivery, and fit feedback. The Agentic Pattern Engine replaces the single-pass Pattern_Engine with an autonomous agent that self-corrects its output using physics simulation.

## Glossary

- **Agent**: The autonomous AI component that orchestrates the full self-correction loop: sloper generation, simulation execution, fit analysis, and geometry recalculation. The Agent operates without human intervention until convergence or iteration limit. Runs headless (no UI).
- **Sloper**: A base bodice pattern block consisting of 2D pattern pieces with seam lines, dart geometry, and construction marks. Generated from body measurements using Parsons-method drafting formulas via PyGarment. For this POC, only bodice/top slopers are in scope.
- **Body_Model**: A 3D mesh representation of a human torso derived from a Measurement_Profile using the SMPL parametric body model. Used as the digital twin target surface for drape simulation.
- **Digital_Twin**: The virtual 3D replica of the customer's body, constructed from their Measurement_Profile via SMPL/SMPL-X. Synonymous with Body_Model in this POC context.
- **Measurement_Profile**: A structured set of body measurements (chest, waist, hip, shoulder width, torso length) provided by a customer. Used as input to both SMPL body model construction and Parsons-method sloper generation.
- **Simulation_Engine**: The physics engine component (NVIDIA Warp or Taichi) that performs GPU-accelerated mass-spring cloth drape simulation of a 2D sloper mapped onto a 3D Body_Model. Runs headless without visual output. Outputs per-vertex stress/strain tensors and collision data.
- **Tension_Map**: A per-vertex scalar field output by the Simulation_Engine representing the magnitude of tensile stress at each point on the simulated garment surface. Values are in Pascals (Pa).
- **Fit_Issue**: A localized region on the Tension_Map where stress exceeds acceptable thresholds or where the garment geometry violates fit constraints (e.g., excess tension at bust, pulling at shoulder, gapping at armhole).
- **Fit_Region**: A named anatomical zone on the Body_Model (bust, waist, shoulder, armhole, side_seam, center_front, center_back) used to localize and classify Fit_Issues. Scoped to bodice/top regions only.
- **Dart**: A triangular fold sewn into a flat pattern piece to create three-dimensional shaping. Defined by placement point, angle, and length.
- **Ease**: The difference between a body measurement and the corresponding garment measurement, providing room for movement and comfort. Measured in centimeters.
- **Correction_Strategy**: A specific geometric adjustment (dart placement, dart angle, dart length, ease redistribution) that the Agent applies to resolve a detected Fit_Issue.
- **Iteration**: One complete cycle of the self-correction loop: simulate the current sloper, analyze the Tension_Map, apply Correction_Strategies, produce an updated sloper.
- **Convergence**: The state where all Fit_Regions on the Tension_Map fall within acceptable stress thresholds and no Fit_Issues remain. The Agent stops iterating upon convergence.
- **Iteration_Limit**: The maximum number of Iterations the Agent may execute before halting. Prevents infinite loops when convergence is not achievable.
- **Agent_Run**: A complete execution of the Agent from initial sloper generation through all Iterations to either convergence or Iteration_Limit, including the full audit trail.
- **Audit_Trail**: The ordered record of every Iteration within an Agent_Run, capturing the sloper state, Tension_Map, detected Fit_Issues, applied Correction_Strategies, and resulting metrics at each step.
- **SMPL**: Skinned Multi-Person Linear model — a parametric 3D body model that represents body shape as a low-dimensional vector of shape parameters. Used with FlexiSMPL to convert customer measurements into a 3D mesh.
- **FlexiSMPL**: A library/method for mapping anthropometric measurements to SMPL shape parameters, enabling construction of a 3D body mesh from a Measurement_Profile.
- **PyGarment**: A parametric sewing pattern DSL (also known as GarmentCode) that defines garment patterns as parameterized programs. Used to generate bodice slopers from body measurements using Parsons-method formulas.
- **Mass_Spring_Model**: The cloth simulation method used by the Simulation_Engine, where the fabric mesh is modeled as a network of point masses connected by springs with stretch, shear, and bend stiffness parameters.
- **DXF**: Drawing Exchange Format — a CAD file format used to export corrected pattern pieces for production cutting. Generated using the ezdxf library.
- **PDF**: Portable Document Format — used to export corrected pattern pieces as printable documents with tiling for home/workshop printing. Generated using the reportlab library.
- **trimesh**: A Python library for loading, processing, and exporting 3D mesh data. Used for mesh I/O operations on the Body_Model.

## Requirements

---

### Requirement 1: Initial Bodice Sloper Generation from Body Measurements

**User Story:** As the MANI platform, I want the Agent to generate an initial bodice sloper from a Measurement_Profile using PyGarment with Parsons-method drafting, so that the self-correction loop has a geometrically valid starting point.

#### Acceptance Criteria

1. WHEN a valid Measurement_Profile is provided, THE Agent SHALL generate an initial bodice sloper using PyGarment with deterministic Parsons-method drafting formulas.
2. THE Agent SHALL produce a bodice sloper containing all required pattern pieces (front bodice, back bodice) with closed outlines, seam lines, dart geometry (placement, angle, length), grain lines, notch marks, and seam allowance markings.
3. THE Agent SHALL include default ease values (bust ease, waist ease) in the initial bodice sloper.
4. IF the Measurement_Profile fails validation, THEN THE Agent SHALL reject the input with a descriptive error identifying the invalid fields before attempting generation.
5. WHEN two identical Measurement_Profiles are provided, THE Agent SHALL produce identical initial bodice slopers (determinism property).
6. THE Agent SHALL represent the bodice sloper using the PyGarment parametric pattern DSL, enabling programmatic modification of dart geometry and ease values in subsequent correction iterations.

---

### Requirement 2: SMPL Digital Twin Construction

**User Story:** As the Agent, I need a 3D Digital_Twin (Body_Model) derived from the customer's measurements using SMPL, so that the Simulation_Engine has a target surface for drape simulation.

#### Acceptance Criteria

1. WHEN a valid Measurement_Profile is provided, THE Agent SHALL construct a Body_Model by mapping measurements to SMPL shape parameters via FlexiSMPL, producing a 3D mesh whose key circumferences (chest, waist, hip) and linear dimensions (shoulder width, torso length) match the Measurement_Profile within a tolerance of 3mm.
2. THE Body_Model SHALL define named Fit_Regions (bust, waist, shoulder, armhole, side_seam, center_front, center_back) as labeled vertex groups on the mesh.
3. THE Agent SHALL use trimesh for mesh I/O operations on the Body_Model.
4. WHEN two identical Measurement_Profiles are provided, THE Agent SHALL produce identical Body_Models (determinism property).
5. FOR ALL valid Measurement_Profiles, extracting circumference and linear measurements from the Body_Model geometry SHALL produce values equivalent to the original Measurement_Profile within a tolerance of 3mm (round-trip property).

---

### Requirement 3: GPU-Accelerated Cloth Drape Simulation

**User Story:** As the Agent, I need to simulate how a 2D bodice sloper drapes over the 3D Body_Model using GPU-accelerated mass-spring simulation, so that I can detect where the garment fits poorly.

#### Acceptance Criteria

1. WHEN a bodice sloper and a Body_Model are provided, THE Simulation_Engine SHALL perform a mass-spring cloth drape simulation using NVIDIA Warp or Taichi that maps the 2D pattern pieces onto the 3D Body_Model surface.
2. THE Simulation_Engine SHALL run headless without any visual output or UI dependencies.
3. THE Simulation_Engine SHALL output a Tension_Map containing per-vertex stress values (in Pascals) for the entire simulated garment surface.
4. THE Simulation_Engine SHALL detect and report collision data where the garment mesh intersects the Body_Model mesh.
5. WHEN the same bodice sloper and Body_Model are provided, THE Simulation_Engine SHALL produce a Tension_Map with stress values that are consistent within a tolerance of 1% between runs (determinism within numerical precision).
6. THE Simulation_Engine SHALL complete a single simulation run within 30 seconds for a bodice sloper on commodity GPU hardware.

---

### Requirement 4: Fit Issue Detection and Classification

**User Story:** As the Agent, I need to analyze the Tension_Map to identify and classify fit problems by bodice region, so that I know which geometry to correct.

#### Acceptance Criteria

1. WHEN a Tension_Map is provided, THE Agent SHALL identify Fit_Issues in any Fit_Region where the stress value exceeds the configurable tension threshold for that region.
2. THE Agent SHALL classify each Fit_Issue by type: excess_tension (garment too tight), insufficient_tension (garment too loose/gapping), and pulling (asymmetric stress indicating distortion).
3. THE Agent SHALL report each Fit_Issue with: the affected Fit_Region name, the issue type, the measured stress value, the threshold value, and the magnitude of the violation.
4. WHEN the Tension_Map contains no stress values exceeding any regional threshold, THE Agent SHALL report zero Fit_Issues and declare convergence.
5. THE Agent SHALL apply consistent classification logic such that the same Tension_Map always produces the same set of Fit_Issues (determinism property).

---

### Requirement 5: Autonomous Bodice Geometry Correction

**User Story:** As the Agent, I need to autonomously recalculate bodice dart geometry and ease distribution to resolve detected Fit_Issues, so that the pattern self-corrects without human intervention.

#### Acceptance Criteria

1. WHEN one or more Fit_Issues are detected, THE Agent SHALL select a Correction_Strategy for each Fit_Issue based on the affected Fit_Region and issue type.
2. THE Agent SHALL support the following Correction_Strategies for bodice patterns: adjust dart placement (move dart apex position), adjust dart angle (widen or narrow dart), adjust dart length (extend or shorten dart), and redistribute ease across bodice Fit_Regions.
3. WHEN a Correction_Strategy is applied, THE Agent SHALL produce an updated bodice sloper via PyGarment that remains geometrically valid (all pieces closed, no overlapping seam lines, seam allowances intact, dart geometry consistent).
4. THE Agent SHALL not apply corrections that would cause any single measurement dimension on the bodice sloper to deviate from the Measurement_Profile by more than the maximum allowable ease tolerance (configurable, default 2cm).
5. WHEN multiple Fit_Issues are detected simultaneously, THE Agent SHALL resolve them in priority order (excess_tension before pulling before insufficient_tension) to avoid conflicting corrections.

---

### Requirement 6: Self-Correction Loop Orchestration

**User Story:** As the MANI platform, I want the Agent to autonomously iterate through simulate-detect-correct cycles until the bodice pattern fits correctly or a safety limit is reached, so that the output is a mathematically guaranteed fit.

#### Acceptance Criteria

1. THE Agent SHALL execute the self-correction loop in the following order: generate initial bodice sloper, simulate drape, detect Fit_Issues, apply corrections, re-simulate, repeating from the detect step until convergence or Iteration_Limit.
2. THE Agent SHALL halt the loop WHEN convergence is achieved (zero Fit_Issues detected).
3. THE Agent SHALL halt the loop WHEN the Iteration_Limit is reached (configurable, default 20 iterations).
4. IF the Agent reaches the Iteration_Limit without convergence, THEN THE Agent SHALL return the best bodice sloper encountered during the run (the iteration with the lowest total stress magnitude) along with a report of remaining Fit_Issues.
5. THE Agent SHALL detect oscillation (a Fit_Issue that alternates between excess_tension and insufficient_tension across consecutive iterations in the same Fit_Region) and reduce correction magnitude by 50% when oscillation is detected.
6. WHEN the Agent achieves convergence, THE Agent SHALL return the final bodice sloper, the total number of iterations executed, and a confirmation that all Fit_Regions are within acceptable thresholds.

---

### Requirement 7: Iteration Audit Trail

**User Story:** As a developer, I want a complete audit trail of every iteration the Agent performs, so that I can debug, analyze, and improve the self-correction logic.

#### Acceptance Criteria

1. THE Agent SHALL record an Audit_Trail entry for each Iteration containing: the iteration number, the bodice sloper state (full geometry), the Tension_Map, the list of detected Fit_Issues, the list of applied Correction_Strategies, and the total stress magnitude.
2. THE Agent SHALL record the initial bodice sloper (iteration 0) in the Audit_Trail before the first simulation.
3. WHEN an Agent_Run completes, THE Agent SHALL return the complete Audit_Trail as part of the result.
4. THE Audit_Trail SHALL preserve chronological ordering such that iteration N always precedes iteration N+1.
5. FOR ALL Agent_Runs, the number of Audit_Trail entries SHALL equal the number of iterations executed plus one (for the initial bodice sloper at iteration 0).

---

### Requirement 8: Tension Threshold Configuration

**User Story:** As a developer, I want to configure tension thresholds per bodice Fit_Region, so that I can tune the Agent's sensitivity for different body areas.

#### Acceptance Criteria

1. THE Agent SHALL accept a configuration object specifying tension thresholds (in Pascals) for each bodice Fit_Region (bust, waist, shoulder, armhole, side_seam, center_front, center_back).
2. WHEN no custom configuration is provided, THE Agent SHALL use default tension thresholds for each bodice Fit_Region.
3. WHEN a custom threshold configuration is provided, THE Agent SHALL use the custom values for fit issue detection in the corresponding Fit_Regions.
4. THE Agent SHALL validate that all threshold values are positive numbers and reject configurations containing zero or negative thresholds with a descriptive error.

---

### Requirement 9: Agent Run Result Reporting

**User Story:** As the MANI platform, I want a structured result from each Agent_Run, so that downstream systems can consume the corrected bodice sloper and understand the correction process.

#### Acceptance Criteria

1. WHEN an Agent_Run completes with convergence, THE Agent SHALL return a result containing: the final corrected bodice sloper, the convergence status (converged), the total iterations executed, and the complete Audit_Trail.
2. WHEN an Agent_Run completes at the Iteration_Limit without convergence, THE Agent SHALL return a result containing: the best bodice sloper (lowest total stress), the convergence status (iteration_limit_reached), the total iterations executed, the remaining Fit_Issues, and the complete Audit_Trail.
3. IF the initial bodice sloper generation fails, THEN THE Agent SHALL return a result containing: the convergence status (generation_failed), zero iterations, and the generation error details.
4. IF the Simulation_Engine fails during any iteration, THEN THE Agent SHALL return a result containing: the convergence status (simulation_failed), the iteration number where failure occurred, the last valid bodice sloper, and the simulation error details.
5. THE Agent SHALL include the total elapsed time (in milliseconds) for the complete Agent_Run in the result.

---

### Requirement 10: Correction Monotonicity and Progress Guarantee

**User Story:** As a developer, I want assurance that the Agent makes measurable progress toward convergence on each iteration, so that the self-correction loop is reliable and predictable.

#### Acceptance Criteria

1. THE Agent SHALL track the total stress magnitude (sum of all stress values exceeding thresholds across all bodice Fit_Regions) at each iteration.
2. WHILE the Agent is not in an oscillation state, THE Agent SHALL produce corrections that reduce the total stress magnitude compared to the previous iteration.
3. IF three consecutive iterations fail to reduce total stress magnitude, THEN THE Agent SHALL flag the run as stalled and halt with the best bodice sloper encountered so far.
4. FOR ALL converged Agent_Runs, the sequence of total stress magnitudes across iterations SHALL be monotonically decreasing (excluding oscillation-dampened iterations).

---

### Requirement 11: Production-Ready DXF/PDF Pattern Export

**User Story:** As the MANI platform, I want the corrected bodice pattern exported as production-ready DXF and PDF files, so that the tailor partner can cut and sew the garment.

#### Acceptance Criteria

1. WHEN an Agent_Run completes (converged or best-effort at Iteration_Limit), THE Agent SHALL export the final corrected bodice sloper as a DXF file using the ezdxf library.
2. WHEN an Agent_Run completes, THE Agent SHALL export the final corrected bodice sloper as a PDF file using the reportlab library.
3. THE DXF export SHALL contain all pattern pieces (front bodice, back bodice) with closed polyline outlines, seam lines, dart lines, grain lines, notch marks, seam allowance markings, and piece labels on separate named layers.
4. THE PDF export SHALL contain all pattern pieces rendered at 1:1 scale with tiling marks for assembly when printed on standard paper sizes (A4/Letter), including seam lines, dart lines, grain lines, notch marks, seam allowance markings, and piece labels.
5. FOR ALL valid corrected bodice slopers, parsing the exported DXF file back into pattern geometry SHALL produce piece outlines equivalent to the original sloper geometry within a tolerance of 0.1mm (round-trip property).
6. THE DXF export SHALL include metadata (customer measurement profile hash, Agent_Run ID, iteration count, convergence status) in the DXF file header or custom properties.
7. THE PDF export SHALL include a cover page with the customer measurement summary, Agent_Run summary (iterations, convergence status), and generation timestamp.
