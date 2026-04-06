# Requirements Document

## Introduction

The MANI Agentic Pattern Engine currently accepts body measurements via hardcoded CLI arguments or JSON profile files. This feature integrates body scanner input so measurements can come from real 3D body scans produced by commercial scanners (3DLOOK, Size Stream, Fit3D, and others). A pluggable adapter architecture maps scanner-specific JSON output to the engine's existing MeasurementProfile and SkirtMeasurementProfile dataclasses. The CLI gains a `--scan` flag for scanner file ingestion with automatic format detection, validation, unit conversion, and garment type hinting. The adapter interface is designed to support future 3D mesh input (OBJ/PLY) even though mesh parsing is not implemented in this milestone.

## Glossary

- **Scanner_Adapter**: A protocol defining the interface for converting scanner-specific JSON output into the engine's canonical measurement profiles. Each commercial scanner format has a concrete adapter implementation.
- **ScannerProfileAdapter**: The top-level component that orchestrates scanner format detection, adapter selection, measurement extraction, validation, and unit conversion.
- **Canonical_Format**: The engine's own scanner JSON schema that serves as the reference format. All commercial adapters map their fields to this canonical structure before conversion to MeasurementProfile or SkirtMeasurementProfile.
- **Scanner_Registry**: A registry of available Scanner_Adapter implementations keyed by scanner format identifier. New adapters are registered via a pluggable pattern.
- **Format_Detector**: The component that examines a scanner JSON file and determines which scanner format produced it, based on structural signatures (field names, metadata keys, version markers).
- **MeasurementProfile**: A frozen dataclass holding bodice body measurements (chest, waist, hip, shoulder_width, torso_length) with validation ranges.
- **SkirtMeasurementProfile**: A frozen dataclass holding skirt-specific body measurements (waist, hip, hip_depth, desired_length) with validation ranges.
- **Unit_Converter**: A utility that converts measurement values between unit systems (inches to centimeters, centimeters to inches) using a fixed conversion factor of 2.54 cm per inch.
- **Garment_Hint**: A suggestion of which garment type (bodice, skirt, or both) is appropriate based on the measurements available in the scanner output.
- **Mesh_Input_Protocol**: A protocol defining the future interface for accepting 3D mesh data (OBJ/PLY point clouds) for body model fitting. Defined but not implemented in this milestone.
- **CLI**: The command-line interface (`cli.py`) that accepts user input and drives the pattern generation engine.
- **Engine**: The agentic self-correction pipeline that generates and refines garment patterns.

## Requirements

### Requirement 1: Canonical Scanner JSON Schema

**User Story:** As a developer, I want a well-defined canonical scanner JSON schema owned by the engine, so that all scanner adapters have a common target format and external integrators have a reference specification.

#### Acceptance Criteria

1. THE Canonical_Format SHALL define required fields: `chest`, `waist`, `hip`, `shoulder_width`, `torso_length`, `hip_depth`, `desired_length`, and `units` (either "cm" or "in").
2. THE Canonical_Format SHALL define optional fields: `arm_length`, `inseam`, `garment_type_hint`, and `scanner_metadata` (an opaque dictionary for scanner-specific data).
3. THE Canonical_Format SHALL be represented as a frozen dataclass with a `validate` method that returns a list of error strings for missing required fields and out-of-range values.
4. WHEN the `units` field is set to "in", THE Canonical_Format SHALL store raw values in inches and defer conversion to the Unit_Converter.
5. THE Canonical_Format SHALL include a `source_scanner` field identifying which scanner or "canonical" produced the data.

### Requirement 2: Scanner Adapter Protocol

**User Story:** As a developer, I want a pluggable adapter protocol for scanner formats, so that adding support for a new scanner requires only implementing a single interface without modifying existing code.

#### Acceptance Criteria

1. THE Scanner_Adapter protocol SHALL define a `scanner_id` property that returns a unique string identifier for the scanner format (e.g., "3dlook", "size_stream", "fit3d", "canonical").
2. THE Scanner_Adapter protocol SHALL define a `can_handle(raw_data: dict) -> bool` method that returns True when the provided JSON structure matches the scanner's expected format.
3. THE Scanner_Adapter protocol SHALL define a `extract(raw_data: dict) -> CanonicalScanData` method that maps scanner-specific fields to the Canonical_Format and returns a CanonicalScanData instance.
4. IF the raw_data is missing fields required by the specific scanner format, THEN THE Scanner_Adapter `extract` method SHALL raise a ValueError with a message listing each missing field.
5. THE Scanner_Adapter protocol SHALL use `typing.Protocol` with `@runtime_checkable` for structural subtyping.

### Requirement 3: Scanner Format Auto-Detection

**User Story:** As a user, I want the engine to automatically detect which scanner produced a JSON file, so that I do not need to specify the scanner format manually.

#### Acceptance Criteria

1. THE Format_Detector SHALL iterate over all registered Scanner_Adapter instances and call `can_handle` on each, returning the first adapter that returns True.
2. WHEN exactly one adapter returns True for a given JSON file, THE Format_Detector SHALL select that adapter for extraction.
3. IF no registered adapter returns True for a given JSON file, THEN THE Format_Detector SHALL return an error listing all registered scanner format identifiers and stating that the format is unrecognized.
4. IF multiple adapters return True for a given JSON file, THEN THE Format_Detector SHALL select the adapter with the highest specificity score, where specificity is defined as the number of scanner-specific marker fields matched.
5. THE Format_Detector SHALL accept a `scanner_hint` parameter that, when provided, skips auto-detection and directly selects the named adapter.

### Requirement 4: Commercial Scanner Adapters

**User Story:** As a user, I want out-of-the-box support for at least two commercial scanner formats, so that I can use scan files from popular body scanners without manual conversion.

#### Acceptance Criteria

1. THE Scanner_Registry SHALL include a 3DLOOK adapter that maps 3DLOOK JSON fields (`front_params.chest`, `front_params.waist`, `front_params.hips`, `front_params.shoulder_width`, `front_params.torso_height`, `front_params.hip_depth`, `unit`) to the Canonical_Format.
2. THE Scanner_Registry SHALL include a Size_Stream adapter that maps Size Stream JSON fields (`measurements.bust_girth`, `measurements.waist_girth`, `measurements.hip_girth`, `measurements.shoulder_breadth`, `measurements.torso_length`, `measurements.hip_depth_length`, `header.units`) to the Canonical_Format.
3. THE 3DLOOK adapter `can_handle` method SHALL return True when the JSON contains a `front_params` key with a nested `chest` field.
4. THE Size_Stream adapter `can_handle` method SHALL return True when the JSON contains a `measurements` key with a nested `bust_girth` field and a `header` key.
5. THE Scanner_Registry SHALL include a Canonical adapter that handles JSON files already in the engine's Canonical_Format (identified by a `source_scanner` field set to "canonical").
6. WHEN a commercial scanner JSON file uses inches as the unit, THE corresponding adapter SHALL set the `units` field to "in" in the extracted CanonicalScanData so the Unit_Converter handles conversion downstream.

### Requirement 5: Unit Conversion

**User Story:** As a user, I want scanner measurements in inches to be automatically converted to centimeters, so that the engine receives values in its expected unit system.

#### Acceptance Criteria

1. THE Unit_Converter SHALL convert inches to centimeters by multiplying by the constant 2.54.
2. THE Unit_Converter SHALL convert centimeters to inches by dividing by the constant 2.54.
3. WHEN a CanonicalScanData instance has `units` set to "in", THE ScannerProfileAdapter SHALL convert all measurement values to centimeters before constructing a MeasurementProfile or SkirtMeasurementProfile.
4. WHEN a CanonicalScanData instance has `units` set to "cm", THE ScannerProfileAdapter SHALL pass measurement values through without conversion.
5. FOR ALL numeric measurement values, converting from inches to centimeters and back to inches SHALL produce a value within 0.001 inches of the original (round-trip property).

### Requirement 6: Measurement Validation

**User Story:** As a user, I want scanner-derived measurements to be validated before they reach the engine, so that out-of-range or missing values are caught early with clear error messages.

#### Acceptance Criteria

1. WHEN a CanonicalScanData instance is converted to a MeasurementProfile, THE ScannerProfileAdapter SHALL call the MeasurementProfile `validate` method and return any errors.
2. WHEN a CanonicalScanData instance is converted to a SkirtMeasurementProfile, THE ScannerProfileAdapter SHALL call the SkirtMeasurementProfile `validate` method and return any errors.
3. IF the scanner output is missing a field required by the target profile type, THEN THE ScannerProfileAdapter SHALL return an error listing each missing field and the profile type that requires the field.
4. IF a measurement value after unit conversion falls outside the anatomically plausible range defined by the target profile, THEN THE ScannerProfileAdapter SHALL return an error identifying the field, the converted value, and the valid range.
5. THE ScannerProfileAdapter SHALL validate that all numeric measurement values are finite (not NaN, not Infinity) before constructing a profile.

### Requirement 7: Garment Type Hinting

**User Story:** As a user, I want the scanner adapter to suggest which garment type is appropriate based on available measurements, so that I do not need to manually specify `--garment` when using scanner input.

#### Acceptance Criteria

1. WHEN the scanner output contains chest, waist, hip, shoulder_width, and torso_length measurements, THE ScannerProfileAdapter SHALL include "bodice" in the garment hint list.
2. WHEN the scanner output contains waist, hip, hip_depth, and desired_length measurements, THE ScannerProfileAdapter SHALL include "skirt" in the garment hint list.
3. WHEN the scanner output contains measurements sufficient for both bodice and skirt profiles, THE ScannerProfileAdapter SHALL include both "bodice" and "skirt" in the garment hint list.
4. WHEN the scanner output contains a `garment_type_hint` field, THE ScannerProfileAdapter SHALL use that value as the primary hint, overriding measurement-based detection.
5. IF the scanner output lacks sufficient measurements for any supported garment type, THEN THE ScannerProfileAdapter SHALL return an error listing the measurements present and the measurements required for each garment type.

### Requirement 8: ScannerProfileAdapter Orchestration

**User Story:** As a developer, I want a single entry-point component that orchestrates format detection, extraction, conversion, validation, and garment hinting, so that callers have a simple API for scanner integration.

#### Acceptance Criteria

1. THE ScannerProfileAdapter SHALL accept raw JSON data (as a Python dict) and return a result containing the constructed measurement profile, the detected garment hints, and any validation warnings.
2. THE ScannerProfileAdapter SHALL call the Format_Detector to select the appropriate Scanner_Adapter.
3. THE ScannerProfileAdapter SHALL call the selected Scanner_Adapter's `extract` method to produce a CanonicalScanData instance.
4. THE ScannerProfileAdapter SHALL call the Unit_Converter when the CanonicalScanData `units` field is "in".
5. THE ScannerProfileAdapter SHALL construct a MeasurementProfile, a SkirtMeasurementProfile, or both, depending on the garment hints.
6. THE ScannerProfileAdapter SHALL return all validation errors collected during extraction, conversion, and profile construction as a list of strings.
7. FOR ALL valid scanner JSON inputs, extracting to CanonicalScanData then serializing the CanonicalScanData to JSON then re-extracting SHALL produce an equivalent CanonicalScanData instance (round-trip property).

### Requirement 9: CLI --scan Flag

**User Story:** As a user, I want a `--scan` CLI flag that accepts a scanner JSON file path, so that I can generate patterns directly from body scan data without manual measurement entry.

#### Acceptance Criteria

1. THE CLI SHALL accept a `--scan` flag followed by a path to a scanner JSON file.
2. THE `--scan` flag SHALL be mutually exclusive with `--chest`, `--waist-primary`, and `--profile` flags.
3. WHEN `--scan` is specified, THE CLI SHALL load the JSON file, pass it to the ScannerProfileAdapter, and use the resulting measurement profile for pattern generation.
4. WHEN `--scan` is specified without `--garment`, THE CLI SHALL use the garment hint from the ScannerProfileAdapter to select the garment type automatically.
5. WHEN `--scan` is specified with `--garment`, THE CLI SHALL use the user-specified garment type, overriding the scanner hint.
6. IF the ScannerProfileAdapter returns validation errors, THEN THE CLI SHALL print each error to stderr and exit with a non-zero status code.
7. THE CLI SHALL accept an optional `--scanner-format` flag that passes a scanner hint to the Format_Detector, bypassing auto-detection.
8. WHEN `--scan` is specified with `--verbose`, THE CLI SHALL print the detected scanner format, extracted measurements, unit conversion details, and garment hint before running the engine.

### Requirement 10: Scanner Adapter Registry and Extensibility

**User Story:** As a developer, I want a registry pattern for scanner adapters, so that new scanner formats can be added by registering a new adapter without modifying existing code.

#### Acceptance Criteria

1. THE Scanner_Registry SHALL maintain an ordered list of Scanner_Adapter instances.
2. THE Scanner_Registry SHALL provide a `register(adapter: Scanner_Adapter) -> None` method that adds an adapter to the registry.
3. THE Scanner_Registry SHALL provide a `get_adapters() -> list[Scanner_Adapter]` method that returns all registered adapters in registration order.
4. THE Scanner_Registry SHALL provide a `get_adapter_by_id(scanner_id: str) -> Scanner_Adapter` method that returns the adapter matching the given identifier.
5. IF `get_adapter_by_id` is called with an unregistered identifier, THEN THE Scanner_Registry SHALL raise a KeyError with a message listing all registered identifiers.
6. THE Scanner_Registry SHALL pre-register the Canonical adapter, the 3DLOOK adapter, and the Size_Stream adapter at module load time.

### Requirement 11: Future Mesh Input Protocol

**User Story:** As a developer, I want the adapter interface to define a protocol for 3D mesh input, so that future milestones can add OBJ/PLY body model fitting without redesigning the adapter architecture.

#### Acceptance Criteria

1. THE Mesh_Input_Protocol SHALL define a `load_mesh(file_path: str) -> MeshData` method signature where MeshData is a frozen dataclass containing vertices (numpy array of shape N×3) and faces (numpy array of shape M×3).
2. THE Mesh_Input_Protocol SHALL define a `extract_measurements(mesh: MeshData) -> CanonicalScanData` method signature for deriving body measurements from a 3D mesh.
3. THE Mesh_Input_Protocol SHALL use `typing.Protocol` for structural subtyping.
4. THE Mesh_Input_Protocol SHALL include a `supported_formats` property returning a list of supported file extensions (at minimum `[".obj", ".ply"]`).
5. THE MeshData dataclass SHALL be defined with `@dataclass(frozen=True)` and placed in the models module alongside existing data models.
6. THE Mesh_Input_Protocol and MeshData SHALL be defined in this milestone but no concrete implementation SHALL be provided. A `NotImplementedError` SHALL be raised if any method is called on a placeholder class.
