# Implementation Plan: Agentic Pattern Engine POC

## Overview

Implement the Agentic Pattern Engine as a Python package (`agentic_pattern_engine/`) with nine components built in dependency order: shared data models first, then leaf components (sloper generator, body model builder), simulation engine, fit detector, geometry corrector, audit trail, exporters, and finally the agent orchestrator that wires everything together. Each component gets property-based tests (hypothesis) alongside implementation. The codebase targets Python 3.11+ with type hints throughout.

## Tasks

- [x] 1. Set up project structure, dependencies, and shared data models
  - [x] 1.1 Create package structure and install dependencies
    - Create `agentic_pattern_engine/` package with `__init__.py`
    - Create `tests/` directory with `conftest.py`
    - Create `pyproject.toml` with dependencies: pygarment, smplx, flexismpl, warp/taichi, ezdxf, reportlab, trimesh, numpy, pytest, hypothesis
    - _Requirements: All_

  - [x] 1.2 Implement shared data models and enums
    - Create `agentic_pattern_engine/models.py` with all frozen dataclasses: `Point2D`, `Line2D`, `DartGeometry`, `PatternPiece`, `BodiceSloper`, `MeasurementProfile` (with RANGES and validation), `FitRegionVertices`, `BodyModel`, `TensionMap`, `SimulationResult`, `FitIssue`, `FitIssueType`, `FitRegion`, `CorrectionType`, `CorrectionStrategy`, `TensionThresholds`, `AuditEntry`, `AuditTrail`, `AgentConfig`, `ConvergenceStatus`, `AgentRunResult`, `ExportMetadata`
    - Implement `MeasurementProfile.validate()` returning list of error strings for out-of-range or missing fields
    - Implement `TensionThresholds.validate()` rejecting zero or negative values
    - _Requirements: 1.4, 8.4_

  - [x] 1.3 Implement Hypothesis custom strategies in conftest.py
    - Create `@composite` strategies: `measurement_profiles()`, `invalid_measurement_profiles()`, `tension_thresholds()`, `bodice_slopers()`, `tension_maps()`, `fit_issues()`, `correction_strategies()`
    - _Requirements: All (testing infrastructure)_

  - [x]* 1.4 Write property tests for MeasurementProfile validation (Property 3) ✅ PBT passed
    - **Property 3: Invalid measurement rejection**
    - For any MeasurementProfile with at least one field outside anatomical range, validation must reject with error identifying the invalid fields
    - **Validates: Requirements 1.4**

  - [x]* 1.5 Write property test for TensionThresholds validation (Property 16) ✅ PBT passed
    - **Property 16: Invalid threshold rejection**
    - For any TensionThresholds with zero or negative values, validation must reject with descriptive error
    - **Validates: Requirements 8.4**

- [x] 2. Implement Sloper Generator
  - [x] 2.1 Implement SloperGenerator with PyGarment integration
    - Create `agentic_pattern_engine/sloper_generator.py`
    - Implement `generate(profile) -> BodiceSloper` using PyGarment with Parsons-method drafting
    - Implement `apply_corrections(sloper, corrections) -> BodiceSloper` producing updated sloper via PyGarment
    - Implement `validate_geometry(sloper) -> list[str]` checking closed outlines, non-overlapping seams, dart consistency
    - Include default bust_ease and waist_ease values
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6, 5.3_

  - [x]* 2.2 Write property test for sloper generation determinism (Property 1)
    - **Property 1: Sloper generation determinism**
    - For any valid MeasurementProfile, `generate(p)` called twice must produce identical BodiceSlopers
    - **Validates: Requirements 1.1, 1.5**

  - [x]* 2.3 Write property test for sloper structural completeness (Property 2)
    - **Property 2: Sloper structural completeness**
    - For any valid MeasurementProfile, generated BodiceSloper must have 2 pieces, each with closed outline, darts, seam lines, grain line, notch marks, positive seam allowance, and positive ease values
    - **Validates: Requirements 1.2, 1.3**

- [x] 3. Implement Body Model Builder
  - [x] 3.1 Implement BodyModelBuilder with SMPL/FlexiSMPL integration
    - Create `agentic_pattern_engine/body_model_builder.py`
    - Implement `build(profile) -> BodyModel` mapping measurements to SMPL shape params via FlexiSMPL, producing 3D mesh with trimesh
    - Implement `extract_measurements(body_model) -> MeasurementProfile` extracting circumferences/linear dims from mesh geometry
    - Define all 7 FitRegion vertex groups (bust, waist, shoulder, armhole, side_seam, center_front, center_back) as non-empty arrays
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x]* 3.2 Write property test for body model measurement round-trip (Property 4) ✅ PBT passed
    - **Property 4: Body model measurement round-trip**
    - For any valid MeasurementProfile, `extract_measurements(build(p))` must match original within 3mm per dimension, and all 7 FitRegion vertex groups must be non-empty
    - **Validates: Requirements 2.1, 2.2, 2.5**

  - [x]* 3.3 Write property test for body model determinism (Property 5) ✅ PBT passed
    - **Property 5: Body model determinism**
    - For any valid MeasurementProfile, `build(p)` called twice must produce identical BodyModels (same vertices, faces, SMPL params)
    - **Validates: Requirements 2.4**

- [x] 4. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Simulation Engine
  - [x] 5.1 Implement SimulationEngine with Warp/Taichi mass-spring simulation
    - Create `agentic_pattern_engine/simulation_engine.py`
    - Implement `simulate(sloper, body_model) -> SimulationResult` performing GPU-accelerated mass-spring cloth drape simulation
    - Run headless without any visual output or UI dependencies
    - Output TensionMap with per-vertex stress values (Pascals) and collision_vertices
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6_

  - [x]* 5.2 Write property test for simulation output completeness (Property 6)
    - **Property 6: Simulation output completeness**
    - For any valid BodiceSloper and BodyModel, simulate must return TensionMap with non-negative per-vertex stresses, collision_vertices array, and positive simulation_time_ms
    - **Validates: Requirements 3.1, 3.3, 3.4**

  - [x]* 5.3 Write property test for simulation determinism (Property 7)
    - **Property 7: Simulation determinism**
    - For any valid BodiceSloper and BodyModel, two simulation runs must produce TensionMaps differing by ≤ 1% relative tolerance
    - **Validates: Requirements 3.5**

- [x] 6. Implement Fit Detector
  - [x] 6.1 Implement FitDetector with tension analysis
    - Create `agentic_pattern_engine/fit_detector.py`
    - Implement `detect(tension_map, body_model, thresholds) -> list[FitIssue]`
    - Classify issues by type: excess_tension, insufficient_tension, pulling
    - Report each issue with region, type, measured_stress, threshold, violation_magnitude
    - Return empty list (convergence) when no stress exceeds thresholds
    - Support custom TensionThresholds and fall back to defaults
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 8.1, 8.2, 8.3_

  - [x]* 6.2 Write property test for fit detection correctness (Property 8)
    - **Property 8: Fit detection correctness**
    - For any TensionMap, BodyModel, and TensionThresholds: every region exceeding threshold must appear in issues, no region within threshold should appear, deterministic output
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**

  - [x]* 6.3 Write property test for custom threshold usage (Property 15)
    - **Property 15: Custom threshold usage**
    - For any valid custom TensionThresholds, FitIssue.threshold must equal the custom value for that region
    - **Validates: Requirements 8.1, 8.3**

- [x] 7. Implement Geometry Corrector
  - [x] 7.1 Implement GeometryCorrector with dart/ease adjustments
    - Create `agentic_pattern_engine/geometry_corrector.py`
    - Implement `plan_corrections(fit_issues, current_sloper, profile, dampening_factor) -> list[CorrectionStrategy]`
    - Support correction types: adjust_dart_placement, adjust_dart_angle, adjust_dart_length, redistribute_ease
    - Enforce priority ordering: excess_tension > pulling > insufficient_tension
    - Implement `validate_corrections(corrections, current_sloper, profile, max_ease_tolerance) -> list[str]`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x]* 7.2 Write property test for correction planning completeness (Property 9)
    - **Property 9: Correction planning completeness and priority ordering**
    - For any non-empty FitIssues list, plan_corrections must return at least one CorrectionStrategy per issue with valid CorrectionType, priority ordered
    - **Validates: Requirements 5.1, 5.2, 5.5**

  - [x]* 7.3 Write property test for correction geometric validity (Property 10)
    - **Property 10: Correction geometric validity**
    - For any valid BodiceSloper and CorrectionStrategies, the updated sloper must pass geometry validation and stay within max_ease_tolerance of the MeasurementProfile
    - **Validates: Requirements 5.3, 5.4**

- [x] 8. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement Audit Trail Recorder
  - [x] 9.1 Implement AuditTrailRecorder
    - Create `agentic_pattern_engine/audit_trail.py`
    - Implement `record(entry: AuditEntry) -> None` appending entries
    - Implement `get_trail() -> AuditTrail` returning complete trail
    - Enforce chronological ordering (iteration N precedes N+1)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x]* 9.2 Write property test for audit trail integrity (Property 11)
    - **Property 11: Audit trail integrity**
    - For any completed AgentRun: first entry is iteration 0 with initial sloper and None tension_map; entries strictly ordered; count equals total_iterations + 1; entries after 0 have non-null tension_map
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**

- [x] 10. Implement DXF and PDF Exporters
  - [x] 10.1 Implement DXFExporter with ezdxf
    - Create `agentic_pattern_engine/dxf_exporter.py`
    - Implement `export(sloper, metadata) -> bytes` with named layers per piece, closed polylines, seam/dart/grain/notch/seam-allowance elements, piece labels, and metadata in custom properties
    - Implement `parse(dxf_bytes) -> BodiceSloper` for round-trip verification
    - _Requirements: 11.1, 11.3, 11.5, 11.6_

  - [x] 10.2 Implement PDFExporter with reportlab
    - Create `agentic_pattern_engine/pdf_exporter.py`
    - Implement `export(sloper, metadata, profile) -> bytes` at 1:1 scale with tiling marks for A4/Letter, cover page with measurement summary, run summary, and timestamp
    - _Requirements: 11.2, 11.4, 11.7_

  - [x]* 10.3 Write property test for DXF export round-trip (Property 20)
    - **Property 20: DXF export round-trip**
    - For any valid BodiceSloper, `parse(export(sloper))` must produce piece outlines equivalent within 0.1mm
    - **Validates: Requirements 11.5**

  - [x]* 10.4 Write property test for DXF export completeness (Property 21)
    - **Property 21: DXF export completeness**
    - For any valid BodiceSloper and ExportMetadata, DXF must contain named layers, all pattern elements, and metadata in custom properties
    - **Validates: Requirements 11.3, 11.6**

  - [x]* 10.5 Write property test for export availability (Property 22)
    - **Property 22: Export availability**
    - For any completed AgentRun with non-null final_sloper, result must include non-null dxf_bytes and pdf_bytes
    - **Validates: Requirements 11.1, 11.2**

- [x] 11. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Implement Agent Orchestrator (self-correction loop)
  - [x] 12.1 Implement AgentOrchestrator core loop
    - Create `agentic_pattern_engine/agent_orchestrator.py`
    - Implement `run(profile, config) -> AgentRunResult` executing the full pipeline: validate input → generate sloper → build body model → record iteration 0 → loop (simulate → detect → check convergence → check limits → check stall → check oscillation → correct → update sloper → record) → export → return result
    - Wire all components: SloperGenerator, BodyModelBuilder, SimulationEngine, FitDetector, GeometryCorrector, AuditTrailRecorder, DXFExporter, PDFExporter
    - Track best sloper (lowest total_stress_magnitude) across iterations
    - Implement oscillation detection (region alternating excess/insufficient across consecutive iterations) with dampening_factor halving
    - Implement stall detection (3 consecutive non-improving iterations → halt)
    - Record elapsed_time_ms for the complete run
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2, 10.3, 10.4_

  - [x]* 12.2 Write property test for iteration limit returns best sloper (Property 12)
    - **Property 12: Iteration limit returns best sloper**
    - For any AgentRun reaching iteration_limit, returned final_sloper must be the one with lowest total_stress_magnitude from the AuditTrail, status must be ITERATION_LIMIT_REACHED, remaining_fit_issues non-empty
    - **Validates: Requirements 6.3, 6.4**

  - [x]* 12.3 Write property test for convergence halts correctly (Property 13)
    - **Property 13: Convergence halts correctly**
    - For any converged AgentRun, final AuditTrail entry must have zero FitIssues, status CONVERGED, remaining_fit_issues empty, total_iterations ≤ iteration_limit
    - **Validates: Requirements 6.2, 6.6**

  - [x]* 12.4 Write property test for oscillation dampening (Property 14)
    - **Property 14: Oscillation dampening**
    - When a FitRegion alternates between excess_tension and insufficient_tension across consecutive iterations, the subsequent CorrectionStrategy must have dampening_factor of 0.5^n
    - **Validates: Requirements 6.5**

  - [x]* 12.5 Write property test for result completeness by status (Property 17)
    - **Property 17: Result completeness by convergence status**
    - For any completed AgentRun: converged → non-null sloper, empty remaining issues; iteration_limit → non-null best sloper, non-empty remaining issues; generation_failed → None sloper, 0 iterations, non-null error; simulation_failed → non-null failed_at_iteration and error_details
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**

  - [x]* 12.6 Write property test for monotonic stress decrease (Property 18)
    - **Property 18: Monotonic stress decrease**
    - For any converged AgentRun, total_stress_magnitude sequence (excluding iteration 0 and oscillation-dampened iterations) must be strictly monotonically decreasing
    - **Validates: Requirements 10.1, 10.2, 10.4**

  - [x]* 12.7 Write property test for stall detection (Property 19)
    - **Property 19: Stall detection and halt**
    - When 3 consecutive iterations fail to reduce total_stress_magnitude (not in oscillation), Agent must halt with STALLED status and return best sloper
    - **Validates: Requirements 10.3**

- [x] 13. Implement CLI entry point
  - [x] 13.1 Create CLI interface
    - Create `agentic_pattern_engine/cli.py` with argument parsing for measurement input (JSON file or CLI args), config overrides (iteration_limit, thresholds), and output paths for DXF/PDF
    - Wire CLI to AgentOrchestrator.run() and print structured result summary
    - _Requirements: All (integration entry point)_

- [x] 14. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (22 total)
- The design uses Python Protocol classes — implementations should conform to these interfaces
- GPU simulation (Warp/Taichi) tests may need mocking on CI without GPU hardware
