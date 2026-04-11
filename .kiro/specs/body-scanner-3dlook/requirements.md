# Requirements Document

## Introduction

The Body Scanner Integration feature enables MANI to accept body scan output files (starting with 3DLOOK Mobile Tailor JSON) instead of requiring manual measurement entry. A pluggable adapter architecture allows future scanner formats to be added without modifying existing code. The system parses scan JSON, maps vendor-specific field names to MANI measurement fields, converts units, detects which garment types the scan supports, and feeds the resulting measurements into the existing pattern engine pipeline via CLI and web app.

## Glossary

- **Scanner_Adapter**: A pluggable component that implements the `ScannerAdapter` protocol to parse a specific scanner vendor's output format and produce a `ScanResult`.
- **ThreeDLook_Adapter**: The `ScannerAdapter` implementation for 3DLOOK Mobile Tailor JSON output.
- **Generic_Adapter**: A fallback `ScannerAdapter` that accepts JSON using MANI's own field names directly.
- **ScanResult**: A frozen dataclass holding parsed measurements, metadata (scanner type, original units), confidence scores, and detected garment type hints.
- **Unit_Converter**: A module providing bidirectional conversion between centimeters and inches for body measurements.
- **Garment_Hint**: An enum indicating which garment types a scan's measurements can support: `bodice_only`, `skirt_only`, `both`, or `insufficient`.
- **MANI_CLI**: The command-line interface at `agentic_pattern_engine/cli.py`.
- **MANI_Web_App**: The FastAPI web application at `web/app.py`.
- **MeasurementProfile**: The existing bodice measurement dataclass (chest, waist, hip, shoulder_width, torso_length).
- **SkirtMeasurementProfile**: The existing skirt measurement dataclass (waist, hip, hip_depth, desired_length).
- **Scan_File**: A JSON file containing body scanner output from a supported vendor.

## Requirements

### Requirement 1: ScannerAdapter Protocol

**User Story:** As a developer, I want a pluggable scanner adapter interface, so that new scanner formats can be added without modifying existing code.

#### Acceptance Criteria

1. THE Scanner_Adapter protocol SHALL define a `parse(data: dict) -> ScanResult` method that accepts a parsed JSON dictionary and returns a ScanResult.
2. THE Scanner_Adapter protocol SHALL define a `can_handle(data: dict) -> bool` method that returns True when the adapter recognizes the JSON format.
3. THE Scanner_Adapter protocol SHALL define a `scanner_name` property that returns a string identifier for the scanner vendor.
4. THE Scanner_Adapter protocol SHALL use `typing.Protocol` with `runtime_checkable` decorator for structural subtyping.

### Requirement 2: ScanResult Data Model

**User Story:** As a developer, I want a structured scan result object, so that parsed measurements and metadata are consistently represented regardless of scanner source.

#### Acceptance Criteria

1. THE ScanResult SHALL store a `measurements` dictionary mapping MANI field names (chest, waist, hip, shoulder_width, torso_length, hip_depth, desired_length) to float values in centimeters.
2. THE ScanResult SHALL store a `source_unit` field indicating the original unit of the scan data ("cm" or "in").
3. THE ScanResult SHALL store a `scanner_type` string identifying which adapter produced the result.
4. THE ScanResult SHALL store an optional `confidence_scores` dictionary mapping field names to float values between 0.0 and 1.0.
5. THE ScanResult SHALL store a `garment_hints` field of type Garment_Hint indicating which garment types the measurements support.
6. THE ScanResult SHALL use `@dataclass(frozen=True)` for immutability.
7. THE ScanResult SHALL store a `raw_data` dictionary preserving the original scanner field names and values before mapping.

### Requirement 3: 3DLOOK Adapter Field Mapping

**User Story:** As a customer using 3DLOOK Mobile Tailor, I want MANI to understand 3DLOOK's field names, so that my scan measurements are correctly mapped to MANI's measurement fields.

#### Acceptance Criteria

1. WHEN a 3DLOOK JSON contains a `bust_girth` or `chest` field, THE ThreeDLook_Adapter SHALL map the value to the MANI `chest` measurement.
2. WHEN a 3DLOOK JSON contains a `waist_girth` or `natural_waist` field, THE ThreeDLook_Adapter SHALL map the value to the MANI `waist` measurement.
3. WHEN a 3DLOOK JSON contains a `hip_girth` or `hips` field, THE ThreeDLook_Adapter SHALL map the value to the MANI `hip` measurement.
4. WHEN a 3DLOOK JSON contains an `across_shoulder` or `shoulder_width` field, THE ThreeDLook_Adapter SHALL map the value to the MANI `shoulder_width` measurement.
5. WHEN a 3DLOOK JSON contains a `back_length` or `center_back_length` field, THE ThreeDLook_Adapter SHALL map the value to the MANI `torso_length` measurement.
6. WHEN a 3DLOOK JSON contains a `hip_depth` or `waist_to_hip` field, THE ThreeDLook_Adapter SHALL map the value to the MANI `hip_depth` measurement.
7. WHEN a 3DLOOK JSON contains an `outseam` or `side_seam_length` field, THE ThreeDLook_Adapter SHALL map the value to the MANI `desired_length` measurement.
8. WHEN multiple alias fields are present for the same MANI measurement, THE ThreeDLook_Adapter SHALL use the first matching alias in the defined priority order.
9. IF a required measurement field has no matching alias in the scan data, THEN THE ThreeDLook_Adapter SHALL omit that field from the ScanResult measurements dictionary rather than inserting a default value.

### Requirement 4: Unit Conversion

**User Story:** As a customer who works in inches, I want MANI to automatically convert scan measurements to the correct unit system, so that the pattern engine receives values in centimeters regardless of the scanner's output unit.

#### Acceptance Criteria

1. WHEN a scan file contains a `units` field set to "in" or "inches", THE Unit_Converter SHALL multiply each measurement value by 2.54 to convert to centimeters.
2. WHEN a scan file contains a `units` field set to "cm" or "centimeters", THE Unit_Converter SHALL pass measurement values through without modification.
3. IF a scan file does not contain a `units` field, THEN THE Unit_Converter SHALL default to centimeters.
4. THE Unit_Converter SHALL provide an `inches_to_cm(value: float) -> float` function that returns `value * 2.54`.
5. THE Unit_Converter SHALL provide a `cm_to_inches(value: float) -> float` function that returns `value / 2.54`.
6. FOR ALL positive float values, converting from inches to centimeters and back to inches SHALL produce a value within 0.01 of the original (round-trip property).

### Requirement 5: Garment Type Detection

**User Story:** As a customer, I want MANI to detect which garment types my scan supports, so that I know whether I can generate a bodice, a skirt, or both from my scan data.

#### Acceptance Criteria

1. WHEN a ScanResult contains chest, waist, hip, shoulder_width, and torso_length measurements, THE ThreeDLook_Adapter SHALL set garment_hints to `both` or `bodice_only` depending on skirt field availability.
2. WHEN a ScanResult contains waist, hip, hip_depth, and desired_length measurements but lacks chest or shoulder_width, THE ThreeDLook_Adapter SHALL set garment_hints to `skirt_only`.
3. WHEN a ScanResult contains all bodice fields (chest, waist, hip, shoulder_width, torso_length) and all skirt fields (waist, hip, hip_depth, desired_length), THE ThreeDLook_Adapter SHALL set garment_hints to `both`.
4. IF a ScanResult lacks sufficient measurements for either garment type, THEN THE ThreeDLook_Adapter SHALL set garment_hints to `insufficient`.

### Requirement 6: ScanResult to MeasurementProfile Conversion

**User Story:** As a developer, I want to convert a ScanResult into the existing MeasurementProfile or SkirtMeasurementProfile, so that scan data integrates with the existing pattern engine without changes to frozen files.

#### Acceptance Criteria

1. WHEN garment_hints is `bodice_only` or `both` and the user requests a bodice, THE ScanResult SHALL produce a valid MeasurementProfile with chest, waist, hip, shoulder_width, and torso_length fields.
2. WHEN garment_hints is `skirt_only` or `both` and the user requests a skirt, THE ScanResult SHALL produce a valid SkirtMeasurementProfile with waist, hip, hip_depth, and desired_length fields.
3. IF the user requests a garment type that the ScanResult garment_hints does not support, THEN THE system SHALL return a descriptive error message listing the missing measurements.
4. THE conversion functions SHALL validate the resulting profile using the existing `validate()` method and return any validation errors.
5. FOR ALL valid ScanResult objects containing bodice fields, converting to MeasurementProfile and extracting the fields back SHALL produce values equal to the ScanResult measurements (round-trip property).

### Requirement 7: Generic JSON Adapter

**User Story:** As a developer, I want a fallback adapter for JSON files that use MANI's own field names, so that users without a supported scanner can still upload measurement files.

#### Acceptance Criteria

1. WHEN a JSON file contains MANI field names directly (chest, waist, hip, shoulder_width, torso_length, hip_depth, desired_length), THE Generic_Adapter SHALL parse the values into a ScanResult.
2. THE Generic_Adapter SHALL set scanner_type to "generic".
3. THE Generic_Adapter `can_handle` method SHALL return True for any JSON dictionary that contains at least a `waist` and `hip` field.
4. WHEN the Generic_Adapter encounters fields not in the MANI field name set, THE Generic_Adapter SHALL ignore the unrecognized fields.

### Requirement 8: Adapter Registry and Auto-Detection

**User Story:** As a developer, I want the system to automatically select the correct adapter for a given scan file, so that users do not need to specify the scanner type manually.

#### Acceptance Criteria

1. THE system SHALL maintain an ordered registry of Scanner_Adapter instances, with vendor-specific adapters checked before the Generic_Adapter.
2. WHEN a scan file is loaded, THE system SHALL iterate through the registry and use the first adapter whose `can_handle` method returns True.
3. IF no adapter in the registry can handle the scan file, THEN THE system SHALL return an error message stating the scan format is not recognized.
4. THE ThreeDLook_Adapter `can_handle` method SHALL return True when the JSON contains a `bust_girth` or `waist_girth` field, or a `source` field containing "3dlook".


### Requirement 9: CLI Scan File Ingestion

**User Story:** As a developer, I want to pass a scan file via the CLI instead of typing individual measurements, so that I can quickly generate patterns from scanner output.

#### Acceptance Criteria

1. THE MANI_CLI SHALL accept a `--scan` argument that takes a file path to a JSON scan file.
2. THE `--scan` argument SHALL be mutually exclusive with `--chest`, `--waist-primary`, and `--profile` arguments.
3. WHEN `--scan` is provided without `--garment`, THE MANI_CLI SHALL use the ScanResult garment_hints to auto-select the garment type, preferring bodice when hints indicate `both`.
4. WHEN `--scan` is provided with `--garment`, THE MANI_CLI SHALL use the specified garment type and return an error if the scan lacks required measurements for that garment.
5. IF the scan file does not exist or contains invalid JSON, THEN THE MANI_CLI SHALL print a descriptive error message and exit with code 1.
6. WHEN `--scan` is provided, THE MANI_CLI SHALL print the detected scanner type, original units, and mapped measurements before running the pattern engine.

### Requirement 10: Web App Scan Upload Endpoint

**User Story:** As a customer using the web app, I want to upload a scan JSON file and have the measurements auto-filled, so that I do not need to manually enter each measurement.

#### Acceptance Criteria

1. THE MANI_Web_App SHALL provide a `POST /api/scan/upload` endpoint that accepts a JSON body containing the scan data.
2. WHEN a valid scan file is uploaded, THE endpoint SHALL return the parsed ScanResult including mapped measurements, scanner type, garment hints, and confidence scores.
3. WHEN a valid scan file is uploaded, THE endpoint SHALL return the measurements in the unit system requested by the client (cm or in) using the Unit_Converter.
4. IF the uploaded scan data cannot be parsed by any registered adapter, THEN THE endpoint SHALL return HTTP 400 with a descriptive error message.
5. THE MANI_Web_App SHALL provide a `POST /api/scan/generate` endpoint that accepts scan data and an optional garment type, parses the scan, builds the profile, and runs the pattern engine in a single request.

### Requirement 11: Scan JSON Parsing and Pretty-Printing

**User Story:** As a developer, I want to parse scan JSON into structured data and format ScanResult back to JSON, so that scan data can be round-tripped for testing and debugging.

#### Acceptance Criteria

1. WHEN a valid JSON string is provided, THE system SHALL parse the string into a dictionary and pass it to the adapter registry for processing.
2. THE system SHALL provide a `scan_result_to_dict(result: ScanResult) -> dict` function that serializes a ScanResult back to a JSON-compatible dictionary.
3. FOR ALL valid ScanResult objects, parsing the serialized dictionary through the Generic_Adapter SHALL produce a ScanResult with equivalent measurements (round-trip property).

### Requirement 12: Test Fixtures

**User Story:** As a developer, I want sample 3DLOOK JSON fixtures, so that I can write reliable tests for the scanner integration.

#### Acceptance Criteria

1. THE test suite SHALL include a fixture file `tests/fixtures/3dlook_full_body.json` containing a complete 3DLOOK scan with all bodice and skirt fields in centimeters.
2. THE test suite SHALL include a fixture file `tests/fixtures/3dlook_upper_only.json` containing a 3DLOOK scan with only upper body (bodice) fields.
3. THE test suite SHALL include a fixture file `tests/fixtures/3dlook_inches.json` containing a 3DLOOK scan with measurements in inches.
4. THE test suite SHALL include a fixture file `tests/fixtures/generic_mani.json` containing a JSON file using MANI's own field names directly.
5. THE test suite SHALL include a fixture file `tests/fixtures/3dlook_minimal.json` containing a 3DLOOK scan with only waist and hip measurements to test the `insufficient` garment hint.
