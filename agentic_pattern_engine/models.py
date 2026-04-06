"""Shared data models and enums for the Agentic Pattern Engine."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Point2D:
    x: float
    y: float


@dataclass(frozen=True)
class Line2D:
    start: Point2D
    end: Point2D


# ---------------------------------------------------------------------------
# Pattern models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DartGeometry:
    apex: Point2D
    angle: float       # degrees
    length: float      # cm


@dataclass(frozen=True)
class PatternPiece:
    piece_id: str
    label: str
    outline: tuple[Point2D, ...]       # Closed polygon (first == last)
    seam_lines: tuple[Line2D, ...]
    darts: tuple[DartGeometry, ...]
    grain_line: Line2D
    notch_marks: tuple[Point2D, ...]
    seam_allowance: float              # cm


@dataclass(frozen=True)
class BodiceSloper:
    sloper_id: str
    profile: "MeasurementProfile"
    front_bodice: PatternPiece
    back_bodice: PatternPiece
    bust_ease: float    # cm
    waist_ease: float   # cm
    metadata: dict      # engine_version, generated_at, etc.


# ---------------------------------------------------------------------------
# Body / measurement models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MeasurementProfile:
    """Customer body measurements for bodice sloper generation."""
    chest: float            # cm
    waist: float            # cm
    hip: float              # cm
    shoulder_width: float   # cm
    torso_length: float     # cm
    arm_length: Optional[float] = None
    inseam: Optional[float] = None

    # Validation ranges (anatomically plausible, cm)
    RANGES: dict = field(
        default=None,   # type: ignore[assignment]
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        # frozen=True prevents normal assignment; use object.__setattr__
        object.__setattr__(self, "RANGES", {
            "chest": (60.0, 180.0),
            "waist": (50.0, 170.0),
            "hip": (60.0, 180.0),
            "shoulder_width": (30.0, 65.0),
            "torso_length": (35.0, 75.0),
        })

    def validate(self) -> list[str]:
        """Return list of error strings for out-of-range or missing fields."""
        errors: list[str] = []
        for fld, (lo, hi) in self.RANGES.items():
            val = getattr(self, fld)
            if val is None:
                errors.append(f"{fld} is missing")
            elif not isinstance(val, (int, float)):
                errors.append(f"{fld} must be numeric, got {type(val).__name__}")
            elif np.isnan(val) or np.isinf(val):
                errors.append(
                    f"{fld}={val} is not a finite number"
                )
            elif val < lo or val > hi:
                errors.append(
                    f"{fld}={val} is out of range [{lo}, {hi}]"
                )
        return errors


@dataclass
class FitRegionVertices:
    """Named vertex groups for each bodice fit region."""
    bust: np.ndarray        # vertex indices
    waist: np.ndarray
    shoulder: np.ndarray
    armhole: np.ndarray
    side_seam: np.ndarray
    center_front: np.ndarray
    center_back: np.ndarray


@dataclass
class BodyModel:
    """3D mesh representation of customer torso."""
    vertices: np.ndarray            # (N, 3) float64
    faces: np.ndarray               # (M, 3) int32
    fit_regions: FitRegionVertices
    smpl_shape_params: np.ndarray   # SMPL beta parameters
    profile: MeasurementProfile


# ---------------------------------------------------------------------------
# Simulation models
# ---------------------------------------------------------------------------

@dataclass
class TensionMap:
    """Per-vertex stress values from cloth simulation."""
    vertex_stresses: np.ndarray     # (N,) float64, Pascals
    collision_vertices: np.ndarray  # vertex indices with body collision
    regional_stresses: dict[str, float] | None = None  # region name -> Pa


@dataclass
class SimulationResult:
    tension_map: TensionMap
    simulation_time_ms: float
    converged: bool  # simulation solver convergence (not fit convergence)


# ---------------------------------------------------------------------------
# Fit analysis models
# ---------------------------------------------------------------------------

class FitIssueType(Enum):
    EXCESS_TENSION = "excess_tension"
    INSUFFICIENT_TENSION = "insufficient_tension"
    PULLING = "pulling"


class FitRegion(Enum):
    BUST = "bust"
    WAIST = "waist"
    SHOULDER = "shoulder"
    ARMHOLE = "armhole"
    SIDE_SEAM = "side_seam"
    CENTER_FRONT = "center_front"
    CENTER_BACK = "center_back"


class CorrectionType(Enum):
    ADJUST_DART_PLACEMENT = "adjust_dart_placement"
    ADJUST_DART_ANGLE = "adjust_dart_angle"
    ADJUST_DART_LENGTH = "adjust_dart_length"
    REDISTRIBUTE_EASE = "redistribute_ease"


@dataclass(frozen=True)
class FitIssue:
    region: FitRegion
    issue_type: FitIssueType
    measured_stress: float      # Pa
    threshold: float            # Pa
    violation_magnitude: float  # Pa (measured - threshold)


@dataclass(frozen=True)
class CorrectionStrategy:
    target_region: FitRegion
    issue_type: FitIssueType
    correction_type: CorrectionType
    magnitude: float            # correction amount (degrees, cm, etc.)
    dampening_factor: float     # 1.0 = full, 0.5 = dampened


# ---------------------------------------------------------------------------
# Configuration models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TensionThresholds:
    """Per-region tension thresholds in Pascals."""
    bust: float = 60.0
    waist: float = 50.0
    shoulder: float = 80.0
    armhole: float = 70.0
    side_seam: float = 55.0
    center_front: float = 50.0
    center_back: float = 50.0

    def validate(self) -> list[str]:
        """Return list of error strings for zero or negative values."""
        errors: list[str] = []
        for fld in ("bust", "waist", "shoulder", "armhole",
                     "side_seam", "center_front", "center_back"):
            val = getattr(self, fld)
            if val <= 0:
                errors.append(
                    f"{fld}={val} must be a positive number (> 0)"
                )
        return errors


@dataclass(frozen=True)
class AgentConfig:
    iteration_limit: int = 20
    oscillation_dampening_factor: float = 0.5
    max_ease_tolerance: float = 2.0       # cm
    stall_threshold: int = 5              # iterations to check for stall
    tension_thresholds: TensionThresholds = field(
        default_factory=TensionThresholds
    )


# ---------------------------------------------------------------------------
# Orchestration / audit models
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    iteration: int
    sloper: BodiceSloper
    tension_map: TensionMap | None          # None for iteration 0
    fit_issues: list[FitIssue]              # Empty for iteration 0
    corrections_applied: list[CorrectionStrategy]  # Empty for iteration 0
    total_stress_magnitude: float           # Sum of stress exceeding thresholds
    pieces: list["PatternPiece"] | None = None  # garment-agnostic output


@dataclass
class AuditTrail:
    entries: list[AuditEntry] = field(default_factory=list)

    @property
    def iteration_count(self) -> int:
        """Number of simulation iterations (excludes iteration 0)."""
        return max(0, len(self.entries) - 1)


class ConvergenceStatus(Enum):
    CONVERGED = "converged"
    ITERATION_LIMIT_REACHED = "iteration_limit_reached"
    STALLED = "stalled"
    GENERATION_FAILED = "generation_failed"
    SIMULATION_FAILED = "simulation_failed"


@dataclass
class AgentRunResult:
    run_id: str
    convergence_status: ConvergenceStatus
    final_sloper: BodiceSloper | None
    total_iterations: int
    audit_trail: AuditTrail
    remaining_fit_issues: list[FitIssue]
    elapsed_time_ms: float
    error_details: str | None = None
    failed_at_iteration: int | None = None
    dxf_bytes: bytes | None = None
    pdf_bytes: bytes | None = None
    final_pieces: list["PatternPiece"] | None = None
    garment_type: str | None = None


@dataclass(frozen=True)
class ExportMetadata:
    profile_hash: str
    run_id: str
    iteration_count: int
    convergence_status: str


# ---------------------------------------------------------------------------
# Skirt models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SkirtMeasurementProfile:
    """Skirt-specific body measurements."""

    waist: float           # cm
    hip: float             # cm
    hip_depth: float       # cm — distance from waist to hip level
    desired_length: float  # cm — waist to hem

    # Validation ranges (anatomically plausible, cm)
    RANGES: dict = field(
        default=None,   # type: ignore[assignment]
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "RANGES", {
            "waist": (50.0, 170.0),
            "hip": (60.0, 180.0),
            "hip_depth": (15.0, 30.0),
            "desired_length": (40.0, 130.0),
        })

    def validate(self) -> list[str]:
        """Return error strings for out-of-range fields."""
        errors: list[str] = []
        for fld, (lo, hi) in self.RANGES.items():
            val = getattr(self, fld)
            if val is None:
                errors.append(f"{fld} is missing")
            elif not isinstance(val, (int, float)):
                errors.append(
                    f"{fld} must be numeric, got {type(val).__name__}"
                )
            elif np.isnan(val) or np.isinf(val):
                errors.append(f"{fld}={val} is not a finite number")
            elif val < lo or val > hi:
                errors.append(
                    f"{fld}={val} is out of range [{lo}, {hi}]"
                )
        return errors


@dataclass(frozen=True)
class SkirtBlock:
    """Skirt block output analogous to BodiceSloper."""

    block_id: str
    profile: SkirtMeasurementProfile
    front_skirt: PatternPiece
    back_skirt: PatternPiece
    waist_ease: float   # cm
    hip_ease: float     # cm
    metadata: dict
