# Requirements Document

## Introduction

Milestone 2 of the MANI Agentic Pattern Engine adds two major capabilities: (1) a long A-line skirt block generator that reuses the existing self-correction engine through a garment-agnostic abstraction, and (2) a pattern grading system that parses uploaded DXF/SVG slopers, computes measurement deltas, and re-grades patterns using the self-correction engine. The existing bodice pipeline must remain fully functional with zero regressions throughout all changes.

## Glossary

- **Engine**: The agentic self-correction pipeline comprising the Orchestrator, Simulation_Engine, Fit_Detector, and Geometry_Corrector working together to iteratively refine a pattern until fit converges.
- **Orchestrator**: The `AgentOrchestrator` component that drives the sense-plan-act self-correction loop: generate pattern → simulate stress → detect fit issues → correct geometry → repeat until converged.
- **Simulation_Engine**: The `MassSpringSimulationEngine` component that computes per-region stress by comparing garment dimensions against body dimensions.
- **Fit_Detector**: The `TensionFitDetector` component that classifies per-region stress values into fit issues (excess tension, insufficient tension, pulling) by comparing against configurable thresholds.
- **Geometry_Corrector**: The `DartEaseGeometryCorrector` component that plans and applies dart/ease corrections to pattern pieces based on detected fit issues.
- **GarmentSpec**: A protocol (abstract interface) that encapsulates garment-specific behavior — pattern generation, stress computation, fit region definitions, correction strategies, and geometry validation — so the Engine can operate on any garment type without code duplication.
- **BodiceGarmentSpec**: The GarmentSpec implementation for bodice slopers, wrapping the existing `ParsonsSloperGenerator` logic.
- **SkirtGarmentSpec**: The GarmentSpec implementation for long A-line skirt blocks.
- **Skirt_Generator**: The component that drafts a 2-piece (front + back) A-line skirt block from waist, hip, hip_depth, and desired_length measurements.
- **Pattern_Parser**: The component that reads an existing DXF or SVG pattern file and extracts pattern pieces with their dimensions, darts, seam lines, and construction marks.
- **Grading_Engine**: The component that computes measurement deltas between a parsed pattern's current dimensions and target body measurements, then applies proportional corrections to re-grade the pattern.
- **PatternPiece**: A frozen dataclass representing a single pattern piece with outline, seam lines, darts, grain line, notch marks, and seam allowance.
- **MeasurementProfile**: A frozen dataclass holding body measurements (chest, waist, hip, shoulder_width, torso_length) with validation ranges.
- **SkirtMeasurementProfile**: An extension of MeasurementProfile that adds skirt-specific fields: hip_depth and desired_length.
- **Fit_Region**: A named anatomical zone on the body model where stress is measured. Bodice regions: bust, waist, shoulder, armhole, side_seam, center_front, center_back. Skirt regions: hip, waist, hem, side_seam.
- **Stress_Model**: The mathematical model that computes per-region stress for a specific garment type. The bodice stress model uses bust/waist circumference ratios and dart relief. The skirt stress model uses waist/hip circumference ratios and flare distribution.
- **Regression_Test**: A test that captures the exact output of the bodice pipeline for a known input profile and asserts that future changes produce identical results.
- **Snapshot_Test**: A test that serializes a BodiceSloper to a deterministic representation and compares against a stored baseline.
- **DXF**: Drawing Exchange Format, a CAD file format used for pattern exchange.
- **SVG**: Scalable Vector Graphics, a vector image format that can represent pattern pieces.
- **Grading**: The process of scaling a base-size pattern up or down to fit different body measurements while preserving proportions and construction details.

## Requirements

### Requirement 1: Bodice Regression Safety Net

**User Story:** As a developer, I want regression and snapshot tests for the existing bodice pipeline, so that I can refactor the engine with confidence that bodice behavior remains unchanged.

#### Acceptance Criteria

1. THE Regression_Test suite SHALL capture the complete output of the bodice pipeline (front PatternPiece, back PatternPiece, bust_ease, waist_ease, dart geometries, seam lines, and convergence status) for at least three distinct MeasurementProfile inputs.
2. THE Snapshot_Test suite SHALL serialize each BodiceSloper to a deterministic JSON representation and compare against a stored baseline file.
3. WHEN a code change alters any bodice pipeline output value by more than 0.001 cm or 0.001 degrees, THE Regression_Test suite SHALL fail with a message identifying the changed field and the magnitude of deviation.
4. THE Regression_Test suite SHALL verify that all 28 existing bodice tests continue to pass after each refactoring step.
5. THE Regression_Test suite SHALL include at least one end-to-end test that runs the full Orchestrator self-correction loop for a bodice profile and asserts convergence status and iteration count match the stored baseline.

### Requirement 2: GarmentSpec Abstraction

**User Story:** As a developer, I want a garment-agnostic protocol that encapsulates garment-specific behavior, so that the Engine can support multiple garment types without code duplication.

#### Acceptance Criteria

1. THE GarmentSpec protocol SHALL define methods for: generating initial pattern pieces from a measurement profile, computing per-region stress given pattern pieces and a measurement profile, listing supported Fit_Region values, planning corrections for detected fit issues, applying corrections to pattern pieces, and validating resulting geometry.
2. THE BodiceGarmentSpec SHALL implement the GarmentSpec protocol by delegating to the existing ParsonsSloperGenerator, bodice stress computation logic, bodice fit regions, and bodice correction strategies.
3. WHEN the Orchestrator receives a BodiceGarmentSpec, THE Orchestrator SHALL produce output identical to the pre-refactor bodice pipeline for the same MeasurementProfile input.
4. THE GarmentSpec protocol SHALL define a `garment_type` property that returns a string identifier (e.g., "bodice", "skirt").
5. THE GarmentSpec protocol SHALL define a `measurement_fields` property that returns the list of required measurement field names for that garment type.
6. THE Orchestrator SHALL accept a GarmentSpec parameter and use its methods instead of directly calling ParsonsSloperGenerator, bodice-specific stress computation, and bodice-specific correction logic.
7. THE Simulation_Engine SHALL accept a stress computation callable provided by the GarmentSpec instead of using hardcoded bodice stress formulas.
8. THE Fit_Detector SHALL accept a list of Fit_Region values provided by the GarmentSpec instead of iterating over all bodice-specific FitRegion enum members.
9. THE Geometry_Corrector SHALL accept correction planning and application callables provided by the GarmentSpec instead of using hardcoded bodice dart/ease correction logic.

### Requirement 3: Skirt Block Pattern Generation

**User Story:** As a pattern maker, I want to generate a long A-line skirt block from body measurements, so that I can produce a production-ready skirt sloper with darts and construction marks.

#### Acceptance Criteria

1. THE Skirt_Generator SHALL accept a SkirtMeasurementProfile containing waist, hip, hip_depth, and desired_length measurements.
2. THE Skirt_Generator SHALL produce two PatternPiece objects: a front skirt piece and a back skirt piece.
3. THE Skirt_Generator SHALL draft waist darts on both front and back pieces, with dart angle and length proportional to the waist-hip differential.
4. THE Skirt_Generator SHALL compute hem flare width based on the desired A-line silhouette, distributing flare evenly between front and back pieces.
5. THE Skirt_Generator SHALL include seam lines for waist seam, side seam, hem, and center front/back on each piece.
6. THE Skirt_Generator SHALL include a vertical grain line and at least two notch marks (waist and hip level) on each piece.
7. THE Skirt_Generator SHALL set a default seam allowance of 1.5 cm on each piece.
8. WHEN any measurement in the SkirtMeasurementProfile is outside anatomically plausible ranges, THE Skirt_Generator SHALL return a validation error listing each out-of-range field.
9. THE SkirtMeasurementProfile SHALL validate that hip_depth is between 15.0 cm and 30.0 cm and desired_length is between 40.0 cm and 130.0 cm.

### Requirement 4: Skirt Stress Model and Self-Correction

**User Story:** As a pattern maker, I want the skirt block to go through the same self-correction loop as the bodice, so that the skirt pattern is automatically adjusted for fit.

#### Acceptance Criteria

1. THE SkirtGarmentSpec SHALL define four Fit_Region values: hip, waist, hem, and side_seam.
2. THE Skirt Stress_Model SHALL compute hip region stress based on the ratio of hip circumference to the garment hip circumference (front_width + back_width) * 2 plus ease.
3. THE Skirt Stress_Model SHALL compute waist region stress based on the ratio of waist circumference to the garment waist circumference plus waist dart relief.
4. THE Skirt Stress_Model SHALL compute hem region stress based on flare distribution relative to the hip-to-hem length.
5. THE Skirt Stress_Model SHALL compute side_seam region stress based on the combined ease and dart relief relative to the hip-waist differential.
6. THE SkirtGarmentSpec SHALL plan corrections that adjust waist dart angle for excess waist tension, adjust waist dart length for insufficient tension, and adjust hem flare angle for hem tension issues.
7. WHEN the Orchestrator runs with a SkirtGarmentSpec, THE Orchestrator SHALL execute the same sense-plan-act loop (simulate → detect → correct → repeat) used for bodice patterns.
8. WHEN the skirt self-correction loop converges, THE Orchestrator SHALL return an AgentRunResult with convergence_status CONVERGED and the corrected skirt pattern pieces.
9. THE SkirtGarmentSpec SHALL define tension thresholds appropriate for skirt fit: hip threshold of 50.0 Pa, waist threshold of 45.0 Pa, hem threshold of 30.0 Pa, and side_seam threshold of 40.0 Pa.

### Requirement 5: CLI Skirt Support

**User Story:** As a user, I want to generate skirt patterns from the command line, so that I can use the engine for skirt production without writing code.

#### Acceptance Criteria

1. THE CLI SHALL accept a `--garment` flag with values "bodice" (default) and "skirt".
2. WHEN `--garment skirt` is specified, THE CLI SHALL require `--waist`, `--hip`, `--hip-depth`, and `--desired-length` arguments.
3. WHEN `--garment skirt` is specified, THE CLI SHALL construct a SkirtMeasurementProfile and pass a SkirtGarmentSpec to the Orchestrator.
4. WHEN `--garment bodice` is specified or `--garment` is omitted, THE CLI SHALL behave identically to the current bodice-only CLI.
5. THE CLI SHALL support `--profile` JSON files that include a `garment_type` field to select the garment spec automatically.
6. THE CLI SHALL include at least two sample skirt measurement profiles as JSON files in a `sample_profiles/` directory.

### Requirement 6: DXF/SVG Pattern Parser

**User Story:** As a pattern maker, I want to upload an existing DXF or SVG pattern file, so that the engine can extract its dimensions for re-grading.

#### Acceptance Criteria

1. WHEN a valid DXF file is provided, THE Pattern_Parser SHALL extract all pattern pieces with their outlines, seam lines, darts (apex, angle, length), grain lines, notch marks, and seam allowance.
2. WHEN a valid SVG file is provided, THE Pattern_Parser SHALL extract all pattern pieces with their outlines, seam lines, darts, grain lines, notch marks, and seam allowance.
3. IF a DXF file contains malformed or missing layer structure, THEN THE Pattern_Parser SHALL return a descriptive error identifying the missing or malformed elements.
4. IF an SVG file contains unsupported path commands or missing pattern metadata, THEN THE Pattern_Parser SHALL return a descriptive error identifying the unsupported elements.
5. THE Pattern_Parser SHALL detect the garment type (bodice or skirt) from pattern piece labels or metadata embedded in the file.
6. FOR ALL valid pattern files, parsing then exporting then parsing SHALL produce pattern pieces with outline coordinates within 0.01 cm of the original (round-trip property).
7. THE Pattern_Parser SHALL support DXF files produced by the existing DXFPatternExporter as a baseline format.

### Requirement 7: Pattern Grading Engine

**User Story:** As a pattern maker, I want to re-grade an existing pattern to fit new body measurements, so that I can resize patterns without manual redrafting.

#### Acceptance Criteria

1. WHEN a parsed pattern and target MeasurementProfile are provided, THE Grading_Engine SHALL compute per-dimension deltas between the pattern's current measurements and the target measurements.
2. THE Grading_Engine SHALL apply proportional scaling to each pattern piece outline, preserving the relative positions of darts, notch marks, and construction details.
3. THE Grading_Engine SHALL pass the scaled pattern through the self-correction Engine (via the appropriate GarmentSpec) to verify and refine fit.
4. WHEN the grading delta for any single dimension exceeds 15.0 cm, THE Grading_Engine SHALL emit a warning that the grade jump is large and results may require manual review.
5. THE Grading_Engine SHALL preserve the original pattern's seam allowance values during grading.
6. THE Grading_Engine SHALL output the re-graded pattern as DXF and PDF using the existing exporters.
7. IF the parsed pattern's garment type cannot be determined, THEN THE Grading_Engine SHALL return an error requesting the user to specify the garment type.

### Requirement 8: CLI Grading Mode

**User Story:** As a user, I want a `--grade` CLI mode that accepts a pattern file and target measurements, so that I can re-grade patterns from the command line.

#### Acceptance Criteria

1. THE CLI SHALL accept a `--grade` flag followed by a path to a DXF or SVG pattern file.
2. WHEN `--grade` is specified, THE CLI SHALL require target body measurements (via `--chest`, `--waist`, etc. or `--profile`).
3. WHEN `--grade` is specified, THE CLI SHALL parse the input pattern, compute grading deltas, run the self-correction loop, and export the re-graded pattern to the output directory.
4. THE CLI SHALL print a summary showing: original dimensions, target dimensions, computed deltas, convergence status, and output file paths.
5. IF the input pattern file format is not recognized, THEN THE CLI SHALL print an error message listing supported formats (DXF, SVG).
6. WHEN `--grade` and `--verbose` are both specified, THE CLI SHALL print the per-iteration audit trail of the grading self-correction loop.

### Requirement 9: Zero-Regression Guarantee

**User Story:** As a developer, I want a guarantee that all existing bodice functionality remains unchanged throughout the Milestone 2 implementation, so that production bodice patterns are never affected.

#### Acceptance Criteria

1. WHILE the GarmentSpec refactoring is in progress, THE Regression_Test suite SHALL pass after every individual commit.
2. WHEN the Orchestrator is refactored to accept a GarmentSpec, THE Orchestrator SHALL default to BodiceGarmentSpec when no GarmentSpec is provided, preserving backward compatibility.
3. THE refactored Simulation_Engine SHALL produce identical regional stress values for bodice inputs as the pre-refactor Simulation_Engine.
4. THE refactored Fit_Detector SHALL produce identical fit issue lists for bodice inputs as the pre-refactor Fit_Detector.
5. THE refactored Geometry_Corrector SHALL produce identical correction strategies and corrected pattern pieces for bodice inputs as the pre-refactor Geometry_Corrector.
6. THE following source files SHALL remain unmodified: `sloper_generator.py`, `body_model_builder.py`, `html_visualizer.py`, `dxf_exporter.py`, `pdf_exporter.py`, `audit_trail.py`.
