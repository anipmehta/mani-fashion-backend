# Implementation Plan: Body Scanner 3DLOOK Integration

## Overview

Integrate 3DLOOK Mobile Tailor body scanner JSON output into the MANI pattern engine using a pluggable adapter architecture. Implementation builds the scanner library first, then integrates into CLI and web app.

## Tasks

- [ ] 1. Scanner core — models, unit converter, adapters, registry
  - [ ] 1.1 Create `agentic_pattern_engine/units.py` (shared unit converter)
    - Implement `inches_to_cm(value: float) -> float`, `cm_to_inches(value: float) -> float`, `convert_measurements(measurements, source_unit)`
    - Handle recognized units: "in", "inches" → convert; "cm", "centimeters", absent → pass through
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ] 1.2 Create `agentic_pattern_engine/scanner/` package with `models.py`, `protocol.py`
    - `GarmentHint` enum: BODICE_ONLY, SKIRT_ONLY, BOTH, INSUFFICIENT
    - `ScanResult` frozen dataclass: measurements, source_unit, scanner_type, garment_hints, raw_data, confidence_scores
    - `ScannerAdapter` protocol: `scanner_name` property, `can_handle(data)`, `parse(data)`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [ ] 1.3 Create `agentic_pattern_engine/scanner/adapters.py` with ThreeDLookAdapter and GenericAdapter
    - ThreeDLookAdapter: FIELD_MAP with priority-ordered aliases, `can_handle` (bust_girth/waist_girth/source=3dlook), `parse` with unit conversion and garment hint detection
    - GenericAdapter: `can_handle` (waist + hip present), `parse` extracts MANI fields, ignores unknown keys
    - _Requirements: 3.1–3.9, 5.1–5.4, 7.1–7.4, 8.4_

  - [ ] 1.4 Create `agentic_pattern_engine/scanner/registry.py` with AdapterRegistry
    - Default adapters: [ThreeDLookAdapter(), GenericAdapter()], `parse` iterates and uses first match, `register` inserts before GenericAdapter
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ] 1.5 Create test fixture JSON files in `tests/fixtures/`
    - `3dlook_full_body.json`, `3dlook_upper_only.json`, `3dlook_inches.json`, `3dlook_minimal.json`, `generic_mani.json`
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [ ] 1.6 Write unit tests for scanner core
    - Test ScanResult immutability, GarmentHint values, ScannerAdapter protocol conformance
    - Test ThreeDLookAdapter field mapping, alias priority, missing field omission, garment hint detection
    - Test GenericAdapter can_handle, field filtering
    - Test AdapterRegistry ordering, auto-detection, ValueError on no match
    - Test unit converter round-trip, convert_measurements with various source_unit values
    - _Requirements: 1.4, 2.6, 3.1–3.9, 4.1–4.6, 5.1–5.4, 7.1–7.4, 8.1–8.4_

  - [ ]* 1.7 Write property tests for scanner core (Properties 1–6, 10–13)
    - **Property 1**: Unit conversion round-trip — **Validates: 4.6**
    - **Property 2**: inches_to_cm correctness — **Validates: 4.1, 4.4**
    - **Property 3**: 3DLOOK field mapping — **Validates: 3.1–3.7**
    - **Property 4**: Alias priority ordering — **Validates: 3.8**
    - **Property 5**: Missing alias omission — **Validates: 3.9**
    - **Property 6**: Garment hint detection — **Validates: 5.1–5.4**
    - **Property 10**: GenericAdapter can_handle — **Validates: 7.3**
    - **Property 11**: GenericAdapter ignores unknown fields — **Validates: 7.4**
    - **Property 12**: ThreeDLook can_handle detection — **Validates: 8.4**
    - **Property 13**: ScanResult invariants — **Validates: 2.1, 2.4, 2.7**

- [ ] 2. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Profile conversion + package exports
  - [ ] 3.1 Create `agentic_pattern_engine/scanner/profile_converter.py`
    - `scan_result_to_bodice_profile(result)` → MeasurementProfile, raises ValueError for incompatible hints/missing fields
    - `scan_result_to_skirt_profile(result)` → SkirtMeasurementProfile, raises ValueError for incompatible hints/missing fields
    - `scan_result_to_dict(result)` → dict serialization
    - Validate resulting profile via existing `validate()` method
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 11.2, 11.3_

  - [ ] 3.2 Update `agentic_pattern_engine/scanner/__init__.py` exports
    - Re-export: ScanResult, GarmentHint, ScannerAdapter, ThreeDLookAdapter, GenericAdapter, AdapterRegistry, profile converter functions
    - Re-export unit converter functions from `agentic_pattern_engine.units` for convenience
    - _Requirements: 1.1, 2.1_

  - [ ] 3.3 Write unit tests for profile conversion
    - Test bodice conversion with valid ScanResult, test skirt conversion, test incompatible hints raise ValueError
    - Test scan_result_to_dict serialization
    - _Requirements: 6.1–6.5, 11.2, 11.3_

  - [ ]* 3.4 Write property tests for profile conversion (Properties 7–9, 14)
    - **Property 7**: Profile conversion validity — **Validates: 6.1, 6.2, 6.4**
    - **Property 8**: Profile conversion round-trip — **Validates: 6.5**
    - **Property 9**: ScanResult serialization round-trip — **Validates: 11.3**
    - **Property 14**: Incompatible garment request error — **Validates: 6.3**

- [ ] 4. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. CLI `--scan` flag integration
  - [ ] 5.1 Add `--scan` argument to CLI in `agentic_pattern_engine/cli.py`
    - Mutually exclusive with `--chest`, `--waist-primary`, `--profile`
    - Read file, json.loads, pass to AdapterRegistry.parse()
    - Print scanner_type, source_unit, mapped measurements
    - Use garment_hints (or `--garment` override) to select profile type, prefer bodice when hints=BOTH
    - Handle FileNotFoundError and ValueError with descriptive message, exit code 1
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ] 5.2 Write unit tests for CLI --scan integration
    - Test mutual exclusivity, auto-select garment type, --garment override, missing file error, invalid JSON error
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 6. Web app scan endpoints
  - [ ] 6.1 Add `/api/scan/upload` and `/api/scan/generate` endpoints to `web/app.py`
    - Pydantic request/response models for both endpoints
    - `/api/scan/upload`: parse scan data, return measurements/scanner_type/garment_hints/confidence_scores, support output_unit conversion via shared `units.py`
    - `/api/scan/generate`: parse scan, build profile, run AgentOrchestrator, return run results with scanner metadata
    - HTTP 400 with descriptive message on ValueError
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 11.1_

  - [ ] 6.2 Write unit tests for web scan endpoints
    - Test /api/scan/upload with 3DLOOK fixture, invalid data returns 400, /api/scan/generate produces output, output_unit conversion
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 7. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass across the entire test suite, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate the 14 correctness properties from the design document
- All new code lives in `agentic_pattern_engine/scanner/` and `agentic_pattern_engine/units.py` — no frozen files are modified
- Unit converter at `agentic_pattern_engine/units.py` is shared across scanner, web app, and CLI
- Test files: `tests/test_units.py`, `tests/test_scanner_models.py`, `tests/test_scanner_adapters.py`, `tests/test_scanner_registry.py`, `tests/test_profile_converter.py`, `tests/test_scanner_cli.py`, `tests/web/test_scan_endpoints.py`
