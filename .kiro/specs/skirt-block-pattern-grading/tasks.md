# Implementation Plan: Skirt Block Pattern Grading

## Overview

Milestone 2 adds skirt block generation, pattern grading, and a garment-agnostic abstraction to the MANI Agentic Pattern Engine. Implementation is split into 9 incremental PRs, each independently testable and mergeable. Every PR preserves bodice regression safety.

## Tasks

- [ ] 1. PR 1 — Bodice regression tests + coding standards steering file
  - [ ] 1.1 Create coding standards steering file in `.kiro/steering/`
    - Define Python style rules, test naming conventions, commit message format, and frozen file list
    - _Requirements: 9.6_

  - [ ] 1.2 Create `tests/baselines/` directory and generate baseline JSON snapshots
    - Run existing bodice pipeline for 3 profiles (standard, plus, petite) and serialize output to `tests/baselines/bodice_standard.json`, `bodice_plus.json`, `bodice_petite.json`
    - Capture: front/back PatternPiece outlines, dart geometries, seam lines, bust_ease, waist_ease, convergence_status, iteration_count
    - _Requirements: 1.1, 1.2_

  - [ ] 1.3 Implement `tests/test_bodice_regression.py` with snapshot and regression tests
    - Snapshot tests: serialize BodiceSloper to JSON, compare against stored baselines
    - Regression tests: assert all output fields match within 0.001 cm / 0.001 degrees tolerance
    - End-to-end test: run full Orchestrator loop, assert convergence status and iteration count match baseline
    - Verify all 28 existing bodice tests still pass
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 1.4 Write property test for bodice serialization determinism
    - **Property 1: Bodice Serialization Determinism**
    - **Validates: Requirements 1.2**

  - [ ] 1.5 Checkpoint — Ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.

- [ ] 2. PR 2 — GarmentSpec abstraction + refactor orchestrator
  - [ ] 2.1 Create `agentic_pattern_engine/garment_spec.py` with `GarmentSpec` protocol
    - Define `typing.Protocol` with `garment_type`, `measurement_fields`, `fit_regions`, `tension_thresholds` properties
    - Define methods: `validate_profile`, `generate_initial_pieces`, `compute_stress`, `plan_corrections`, `apply_corrections`, `validate_geometry`
    - _Requirements: 2.1, 2.4, 2.5_

  - [ ] 2.2 Implement `BodiceGarmentSpec` in `garment_spec.py`
    - Delegate to existing `ParsonsSloperGenerator`, bodice stress logic, and bodice correction logic
    - Do NOT modify frozen files — wrap existing classes
    - _Requirements: 2.2, 2.3_

  - [ ] 2.3 Refactor `AgentOrchestrator` to accept optional `GarmentSpec` parameter
    - Default to `BodiceGarmentSpec` when no spec provided (backward compatibility)
    - Call `spec.generate_initial_pieces()` instead of direct sloper generator calls
    - Call `spec.compute_stress()` in the simulation step
    - Call `spec.plan_corrections()` and `spec.apply_corrections()` in the correction step
    - Add `final_pieces` and `garment_type` fields to `AgentRunResult`
    - _Requirements: 2.6, 9.2_

  - [ ] 2.4 Write unit tests for `GarmentSpec` protocol and `BodiceGarmentSpec` in `tests/test_garment_spec.py`
    - Test protocol conformance via `isinstance` check with `runtime_checkable`
    - Test `BodiceGarmentSpec` produces identical output to pre-refactor pipeline
    - Test orchestrator with explicit `BodiceGarmentSpec` matches pre-refactor output
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ]* 2.5 Write property test for GarmentSpec structural conformance
    - **Property 3: GarmentSpec Structural Conformance**
    - **Validates: Requirements 2.1, 2.4, 2.5**

  - [ ]* 2.6 Write property test for BodiceGarmentSpec orchestrator regression
    - **Property 2: BodiceGarmentSpec Orchestrator Regression**
    - **Validates: Requirements 2.3, 9.3, 9.4, 9.5**

  - [ ] 2.7 Run bodice regression suite — confirm zero regressions
    - Ensure all tests in `test_bodice_regression.py` and all 28 existing tests pass
    - _Requirements: 9.1_

  - [ ] 2.8 Checkpoint — Ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. PR 3 — Refactor simulation/detector/corrector to accept garment spec
  - [ ] 3.1 Refactor `MassSpringSimulationEngine.simulate` to accept a `stress_fn` callable
    - Add `stress_fn` parameter; when provided, use it instead of `_compute_regional_stresses`
    - Existing bodice path remains as fallback when `stress_fn` is `None`
    - _Requirements: 2.7, 9.3_

  - [ ] 3.2 Refactor `TensionFitDetector.detect` to accept `spec_regions` and `spec_thresholds`
    - Add `spec_regions: list[str]` and `spec_thresholds: dict[str, float]` keyword params
    - When provided, iterate only over `spec_regions` instead of all `FitRegion` enum members
    - Legacy path unchanged when params are `None`
    - _Requirements: 2.8, 9.4_

  - [ ] 3.3 Refactor `DartEaseGeometryCorrector` to accept correction callables
    - Add `plan_corrections_fn` and `apply_corrections_fn` callable parameters
    - When provided, delegate to callables instead of hardcoded bodice logic
    - Legacy path unchanged when params are `None`
    - _Requirements: 2.9, 9.5_

  - [ ] 3.4 Update `BodiceGarmentSpec` to wire refactored engine components
    - Pass bodice stress method as `stress_fn`, bodice regions as `spec_regions`, bodice correction methods as callables
    - _Requirements: 2.2, 2.3_

  - [ ] 3.5 Write unit tests for refactored engine components in existing test files
    - Add tests to `test_simulation_engine.py` for `stress_fn` callable path
    - Add tests to `test_fit_detector.py` for `spec_regions` filtering
    - Add tests to `test_geometry_corrector.py` for correction callable path
    - _Requirements: 2.7, 2.8, 2.9_

  - [ ]* 3.6 Write property test for fit detector region filtering
    - **Property 4: Fit Detector Region Filtering**
    - **Validates: Requirements 2.8**

  - [ ] 3.7 Run bodice regression suite — confirm zero regressions
    - Ensure all tests in `test_bodice_regression.py` and all 28 existing tests pass
    - _Requirements: 9.1, 9.3, 9.4, 9.5_

  - [ ] 3.8 Checkpoint — Ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. PR 4 — Skirt data models + skirt generator
  - [ ] 4.1 Add `SkirtMeasurementProfile`, `SkirtBlock`, and `SkirtFitRegion` to `models.py`
    - `SkirtMeasurementProfile`: frozen dataclass with waist, hip, hip_depth, desired_length + validation ranges
    - `SkirtBlock`: frozen dataclass with block_id, profile, front_skirt, back_skirt, waist_ease, hip_ease, metadata
    - Validation: hip_depth [15.0, 30.0], desired_length [40.0, 130.0], waist [50.0, 170.0], hip [60.0, 180.0]
    - _Requirements: 3.1, 3.8, 3.9_

  - [ ] 4.2 Write unit tests for `SkirtMeasurementProfile` validation in `tests/test_models.py`
    - Test valid profiles pass validation
    - Test each out-of-range field produces correct error message
    - Test boundary values at range edges
    - _Requirements: 3.8, 3.9_

  - [ ]* 4.3 Write property test for skirt measurement validation
    - **Property 8: Skirt Measurement Validation**
    - **Validates: Requirements 3.8, 3.9**

  - [ ] 4.4 Create `agentic_pattern_engine/skirt_generator.py` with `SkirtGenerator`
    - `generate(profile)` → returns 2 `PatternPiece` objects (front + back)
    - `_draft_front` / `_draft_back`: closed outline polygon, waist darts, A-line flare
    - `_compute_dart_geometry`: dart angle/length proportional to waist-hip differential
    - `_compute_hem_flare`: hem flare width for A-line silhouette, even front/back distribution
    - Each piece: seam lines (waist, side, hem, center), vertical grain line, 2+ notch marks (waist + hip level), 1.5 cm seam allowance
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ] 4.5 Write unit tests for `SkirtGenerator` in `tests/test_skirt_generator.py`
    - Test standard profile produces 2 pieces with correct structure
    - Test dart geometry scales with waist-hip differential
    - Test hem flare is symmetric front/back
    - Test seam lines, grain line, notch marks, seam allowance present
    - Test out-of-range profile returns validation error
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [ ]* 4.6 Write property test for skirt generator output invariants
    - **Property 5: Skirt Generator Output Invariants**
    - **Validates: Requirements 3.1, 3.2, 3.5, 3.6, 3.7**

  - [ ]* 4.7 Write property test for skirt dart proportionality
    - **Property 6: Skirt Dart Proportionality**
    - **Validates: Requirements 3.3**

  - [ ]* 4.8 Write property test for skirt hem flare symmetry
    - **Property 7: Skirt Hem Flare Symmetry**
    - **Validates: Requirements 3.4**

  - [ ] 4.9 Checkpoint — Ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. PR 5 — Skirt stress model + corrections + orchestrator integration
  - [ ] 5.1 Implement `SkirtGarmentSpec` in `skirt_generator.py`
    - `garment_type` → `"skirt"`, `measurement_fields` → `["waist", "hip", "hip_depth", "desired_length"]`
    - `fit_regions` → `["hip", "waist", "hem", "side_seam"]`
    - `tension_thresholds` → hip: 50.0, waist: 45.0, hem: 30.0, side_seam: 40.0
    - `validate_profile`: delegate to `SkirtMeasurementProfile.validate()`
    - `generate_initial_pieces`: delegate to `SkirtGenerator.generate()`
    - _Requirements: 4.1, 4.9_

  - [ ] 5.2 Implement skirt stress model in `SkirtGarmentSpec.compute_stress`
    - Hip stress: ratio of body hip circumference to garment hip circumference `(front_width + back_width) * 2` plus ease
    - Waist stress: ratio of body waist circumference to garment waist circumference plus waist dart relief
    - Hem stress: flare distribution relative to hip-to-hem length
    - Side seam stress: combined ease and dart relief relative to hip-waist differential
    - _Requirements: 4.2, 4.3, 4.4, 4.5_

  - [ ] 5.3 Implement skirt correction strategies in `SkirtGarmentSpec.plan_corrections` and `apply_corrections`
    - Excess waist tension → adjust waist dart angle
    - Insufficient tension → adjust waist dart length
    - Hem tension → adjust hem flare angle
    - _Requirements: 4.6_

  - [ ] 5.4 Wire `SkirtGarmentSpec` through the orchestrator and verify self-correction loop
    - Pass `SkirtGarmentSpec` to `AgentOrchestrator`, run loop for a standard skirt profile
    - Verify convergence produces `AgentRunResult` with `CONVERGED` status and corrected skirt pieces
    - _Requirements: 4.7, 4.8_

  - [ ] 5.5 Write unit tests for `SkirtGarmentSpec` in `tests/test_skirt_garment_spec.py`
    - Test stress computation for known profile produces expected per-region values
    - Test correction planning maps issue types to correct correction strategies
    - Test full orchestrator loop with `SkirtGarmentSpec` converges
    - Test `AgentRunResult` has `convergence_status == CONVERGED`, non-empty `final_pieces`, empty `remaining_fit_issues`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [ ]* 5.6 Write property test for skirt stress model monotonicity
    - **Property 9: Skirt Stress Model Monotonicity**
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5**

  - [ ]* 5.7 Write property test for skirt correction type mapping
    - **Property 10: Skirt Correction Type Mapping**
    - **Validates: Requirements 4.6**

  - [ ]* 5.8 Write property test for skirt convergence result integrity
    - **Property 11: Skirt Convergence Result Integrity**
    - **Validates: Requirements 4.8**

  - [ ] 5.9 Run bodice regression suite — confirm zero regressions
    - Ensure all bodice tests still pass after skirt integration
    - _Requirements: 9.1_

  - [ ] 5.10 Checkpoint — Ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. PR 6 — CLI `--garment skirt` + skirt sample profiles
  - [ ] 6.1 Add `--garment` flag to CLI in `agentic_pattern_engine/cli.py`
    - Accept values `"bodice"` (default) and `"skirt"`
    - When `--garment bodice` or omitted, behavior is identical to current CLI
    - When `--garment skirt`, require `--waist`, `--hip`, `--hip-depth`, `--desired-length` arguments
    - Construct `SkirtMeasurementProfile` and pass `SkirtGarmentSpec` to orchestrator
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ] 6.2 Add `--profile` JSON support for garment type auto-selection
    - Parse `garment_type` field from profile JSON to select the correct `GarmentSpec`
    - _Requirements: 5.5_

  - [ ] 6.3 Create sample skirt profiles in `sample_profiles/`
    - `sample_profiles/skirt_standard.json` and `sample_profiles/skirt_petite.json`
    - Each includes `garment_type: "skirt"`, waist, hip, hip_depth, desired_length
    - _Requirements: 5.6_

  - [ ] 6.4 Write unit tests for CLI skirt support in `tests/test_cli_skirt.py`
    - Test `--garment skirt` with required args produces skirt output
    - Test `--garment skirt` without required args prints error
    - Test `--profile` with skirt JSON auto-selects skirt spec
    - Test `--garment bodice` and omitted `--garment` produce identical output
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 6.5 Write property test for CLI backward compatibility
    - **Property 12: CLI Backward Compatibility**
    - **Validates: Requirements 5.4**

  - [ ] 6.6 Checkpoint — Ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. PR 7 — DXF/SVG pattern parser
  - [ ] 7.1 Create `agentic_pattern_engine/pattern_parser.py` with `PatternParser`
    - `parse(file_path)`: auto-detect format by extension, delegate to `parse_dxf` or `parse_svg`
    - Return `ParseResult` with pieces, garment_type, source_format, warnings, errors
    - _Requirements: 6.1, 6.2_

  - [ ] 7.2 Implement `parse_dxf` method
    - Extract pattern pieces: outlines, seam lines, darts (apex, angle, length), grain lines, notch marks, seam allowance
    - Support DXF files produced by existing `DXFPatternExporter` as baseline format
    - Return descriptive errors for malformed/missing layer structure
    - _Requirements: 6.1, 6.3, 6.7_

  - [ ] 7.3 Implement `parse_svg` method
    - Extract pattern pieces from SVG path elements with metadata in data attributes or embedded JSON
    - Return descriptive errors for unsupported path commands or missing metadata
    - _Requirements: 6.2, 6.4_

  - [ ] 7.4 Implement `_detect_garment_type` from piece labels/metadata
    - Detect "bodice" or "skirt" from piece labels or file metadata
    - Return `None` when garment type cannot be determined
    - _Requirements: 6.5_

  - [ ] 7.5 Add `ParseResult` dataclass to `models.py`
    - Fields: pieces, garment_type, source_format, source_profile, warnings, errors
    - _Requirements: 6.1, 6.2_

  - [ ] 7.6 Write unit tests for `PatternParser` in `tests/test_pattern_parser.py`
    - Test DXF parsing with a file exported by `DXFPatternExporter`
    - Test SVG parsing with a valid SVG pattern file
    - Test malformed DXF returns descriptive errors
    - Test malformed SVG returns descriptive errors
    - Test garment type detection from piece labels
    - Test unrecognized format returns error
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.7_

  - [ ]* 7.7 Write property test for parse-export round trip
    - **Property 13: Pattern Parse-Export Round Trip**
    - **Validates: Requirements 6.1, 6.2, 6.6, 6.7**

  - [ ]* 7.8 Write property test for parser error handling
    - **Property 14: Parser Error Handling**
    - **Validates: Requirements 6.3, 6.4**

  - [ ]* 7.9 Write property test for parser garment type detection
    - **Property 15: Parser Garment Type Detection**
    - **Validates: Requirements 6.5**

  - [ ] 7.10 Checkpoint — Ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. PR 8 — Grading engine
  - [ ] 8.1 Add `GradingResult` dataclass to `models.py`
    - Fields: original_pieces, graded_pieces, deltas, run_result, warnings
    - _Requirements: 7.1_

  - [ ] 8.2 Create `agentic_pattern_engine/grading_engine.py` with `GradingEngine`
    - `__init__` accepts an `AgentOrchestrator` instance
    - `grade(parsed_pieces, source_profile, target_profile, garment_type)` → `GradingResult`
    - _Requirements: 7.1, 7.3_

  - [ ] 8.3 Implement `_compute_deltas` method
    - Compute `target.field - source.field` for every shared measurement field
    - _Requirements: 7.1_

  - [ ] 8.4 Implement `_apply_proportional_scaling` method
    - Scale pattern piece outlines proportionally, preserving relative dart positions, notch marks, and construction details
    - Preserve original seam allowance values
    - _Requirements: 7.2, 7.5_

  - [ ] 8.5 Wire grading through self-correction engine
    - After proportional scaling, pass scaled pieces through orchestrator with appropriate `GarmentSpec` for fit refinement
    - Emit warning when any single delta exceeds 15.0 cm
    - Return error when garment type cannot be determined
    - Export re-graded pattern as DXF and PDF using existing exporters
    - _Requirements: 7.3, 7.4, 7.6, 7.7_

  - [ ] 8.6 Write unit tests for `GradingEngine` in `tests/test_grading_engine.py`
    - Test delta computation for known source/target profiles
    - Test proportional scaling preserves dart ratios and seam allowance
    - Test large delta (> 15 cm) produces warning
    - Test unknown garment type returns error
    - Test grading runs self-correction and returns converged result
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [ ]* 8.7 Write property test for grading delta computation
    - **Property 16: Grading Delta Computation**
    - **Validates: Requirements 7.1, 7.4**

  - [ ]* 8.8 Write property test for grading preserves construction proportions
    - **Property 17: Grading Preserves Construction Proportions**
    - **Validates: Requirements 7.2, 7.5**

  - [ ] 8.9 Checkpoint — Ensure all tests pass
    - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. PR 9 — CLI `--grade` mode + API surface
  - [ ] 9.1 Add `--grade` flag to CLI in `agentic_pattern_engine/cli.py`
    - Accept a path to a DXF or SVG pattern file
    - Require target body measurements via `--chest`, `--waist`, etc. or `--profile`
    - Parse input pattern, compute grading deltas, run self-correction, export re-graded pattern
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ] 9.2 Implement grading summary output
    - Print: original dimensions, target dimensions, computed deltas, convergence status, output file paths
    - When `--verbose` is specified, print per-iteration audit trail
    - _Requirements: 8.4, 8.6_

  - [ ] 9.3 Implement format validation and error handling
    - Print error listing supported formats (DXF, SVG) when input format is not recognized
    - _Requirements: 8.5_

  - [ ] 9.4 Write unit tests for CLI grading mode in `tests/test_cli_skirt.py`
    - Test `--grade` with valid DXF file and target measurements produces graded output
    - Test `--grade` without target measurements prints error
    - Test `--grade` with unrecognized format prints supported formats error
    - Test `--grade --verbose` prints per-iteration audit trail
    - Test grading summary contains all required fields
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 9.5 Write property test for CLI grading summary completeness
    - **Property 18: CLI Grading Summary Completeness**
    - **Validates: Requirements 8.4**

  - [ ] 9.6 Final checkpoint — Ensure all tests pass
    - Ensure all tests pass across the entire test suite, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each top-level task (1–9) maps to one PR, independently testable and mergeable
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties from the design document
- Bodice regression suite must pass at every checkpoint (Requirements 9.1)
- Frozen files (`sloper_generator.py`, `body_model_builder.py`, `html_visualizer.py`, `dxf_exporter.py`, `pdf_exporter.py`, `audit_trail.py`) must NOT be modified (Requirements 9.6)
- Git workflow: feature branch `feat/skirt-block-pattern-grading`, conventional commits, incremental pushes per task
