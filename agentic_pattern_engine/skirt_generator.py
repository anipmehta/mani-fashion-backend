"""Skirt Generator — A-line skirt block drafting from measurements.

Drafts a 2-piece (front + back) A-line skirt block following standard
flat-pattern drafting:

1. Rectangle: quarter-hip width × desired length
2. Center front/back = straight vertical (cut on fold)
3. Waist is narrower than hip — straight line from CF to side waist
4. Side seam: straight from waist, gentle hip curve blending into
   the wider hip width, then straight A-line flare to hem
5. Hem: nearly straight, very slight upward rise at side seam
6. Front: 1 dart (40% intake). Back: 2 darts (60% intake)
7. Only curves: hip transition on side seam, slight hem curve
"""

from __future__ import annotations

import math

from agentic_pattern_engine.models import (
    CorrectionStrategy,
    DartGeometry,
    FitIssue,
    Line2D,
    MeasurementProfile,
    PatternPiece,
    Point2D,
    SkirtMeasurementProfile,
)


class SkirtGenerator:
    """Draft a 2-piece A-line skirt block from measurements."""

    DEFAULT_SEAM_ALLOWANCE = 1.5
    HEM_FLARE_SCALE = 0.12
    HIP_EASE = 1.5                 # cm
    FRONT_DART_RATIO = 0.40
    BACK_DART_RATIO = 0.60
    FRONT_DART_POSITION = 0.38
    BACK_DART1_POSITION = 0.30
    BACK_DART2_POSITION = 0.60
    DART_LENGTH_RATIO_FRONT = 0.50
    DART_LENGTH_RATIO_BACK1 = 0.65
    DART_LENGTH_RATIO_BACK2 = 0.55
    MIN_DART_ANGLE = 2.0
    MAX_DART_ANGLE = 20.0
    SIDE_WAIST_RISE_FRONT = 0.5   # cm — front side waist rise
    SIDE_WAIST_RISE_BACK = 1.0    # cm — back side waist rise (deeper)
    HEM_SIDE_RISE = 0.8           # cm
    HIP_CURVE_POINTS = 6

    def generate(
        self, profile: SkirtMeasurementProfile,
    ) -> list[PatternPiece]:
        """Generate front and back skirt pieces."""
        errors = profile.validate()
        if errors:
            raise ValueError(
                f"Invalid skirt profile: {'; '.join(errors)}"
            )
        return [
            self._draft_piece(profile, is_front=True),
            self._draft_piece(profile, is_front=False),
        ]

    def _draft_piece(
        self,
        profile: SkirtMeasurementProfile,
        is_front: bool,
    ) -> PatternPiece:
        """Draft one skirt piece (front or back)."""
        qtr_hip = (profile.hip + self.HIP_EASE) / 4.0
        qtr_waist = profile.waist / 4.0
        length = profile.desired_length
        hip_d = profile.hip_depth
        flare = self._compute_hem_flare(profile)
        dart_ratio = self.FRONT_DART_RATIO if is_front else self.BACK_DART_RATIO

        diff = qtr_hip - qtr_waist
        dart_intake = diff * dart_ratio

        # Back waist rises more at the side seam
        waist_rise = (
            self.SIDE_WAIST_RISE_FRONT if is_front
            else self.SIDE_WAIST_RISE_BACK
        )

        # Side waist x: waist quarter + dart intake removed
        side_waist_x = qtr_waist + dart_intake
        side_waist_y = -waist_rise

        # Construction points
        c_waist = Point2D(0.0, 0.0)           # center waist
        s_waist = Point2D(side_waist_x, side_waist_y)  # side waist
        s_hip = Point2D(qtr_hip, hip_d)        # side hip
        s_hem = Point2D(qtr_hip + flare, length - self.HEM_SIDE_RISE)
        c_hem = Point2D(0.0, length)           # center hem
        c_hip = Point2D(0.0, hip_d)            # center hip

        # Build outline
        pts: list[Point2D] = []

        # 1. Waist: center → side (gentle curve, dips at side)
        pts.append(c_waist)
        pts.extend(self._gentle_curve(
            c_waist, s_waist,
            bow_y=waist_rise * 0.3,  # slight upward bow
            bow_direction=-1,  # curve upward (negative y)
        ))

        # 2. Side seam: waist → hip (smooth hip curve)
        pts.extend(self._hip_curve(s_waist, s_hip))

        # 3. Side seam: hip → hem (straight A-line flare)
        pts.append(s_hem)

        # 4. Hem: side → center (gentle curve, rises at side)
        pts.extend(self._gentle_curve(
            s_hem, c_hem,
            bow_y=1.0,  # 1cm downward bow at center
            bow_direction=1,  # curve downward (positive y)
        ))

        # 5. Center: hem → waist (straight vertical)
        pts.append(c_hip)
        pts.append(c_waist)

        outline = tuple(pts)

        # Darts
        if is_front:
            darts = (self._make_dart(
                qtr_waist, dart_intake,
                self.FRONT_DART_POSITION,
                hip_d * self.DART_LENGTH_RATIO_FRONT,
            ),)
        else:
            intake1 = dart_intake * 0.55
            intake2 = dart_intake * 0.45
            darts = (
                self._make_dart(
                    qtr_waist, intake1,
                    self.BACK_DART1_POSITION,
                    hip_d * self.DART_LENGTH_RATIO_BACK1,
                ),
                self._make_dart(
                    qtr_waist, intake2,
                    self.BACK_DART2_POSITION,
                    hip_d * self.DART_LENGTH_RATIO_BACK2,
                ),
            )

        seam_lines = (
            Line2D(c_waist, s_waist),
            Line2D(s_waist, s_hip),
            Line2D(s_hip, s_hem),
            Line2D(s_hem, c_hem),
            Line2D(c_hem, c_hip),
            Line2D(c_hip, c_waist),
        )

        grain_line = Line2D(
            start=Point2D(qtr_hip * 0.5, 3.0),
            end=Point2D(qtr_hip * 0.5, length - 3.0),
        )

        notch_marks = (
            Point2D(qtr_waist * 0.5, 0.0),
            Point2D(qtr_hip * 0.5, hip_d),
        )

        piece_id = "front_skirt" if is_front else "back_skirt"
        label = "Front Skirt" if is_front else "Back Skirt"

        return PatternPiece(
            piece_id=piece_id,
            label=label,
            outline=outline,
            seam_lines=seam_lines,
            darts=darts,
            grain_line=grain_line,
            notch_marks=notch_marks,
            seam_allowance=self.DEFAULT_SEAM_ALLOWANCE,
        )

    def _hip_curve(
        self,
        waist_pt: Point2D,
        hip_pt: Point2D,
    ) -> list[Point2D]:
        """Gentle outward curve from side waist to side hip."""
        t_ctrl = 0.4
        mx = waist_pt.x + (hip_pt.x - waist_pt.x) * t_ctrl
        my = waist_pt.y + (hip_pt.y - waist_pt.y) * t_ctrl
        offset = 1.0  # cm
        ctrl = Point2D(mx + offset, my)

        pts: list[Point2D] = []
        n = self.HIP_CURVE_POINTS
        for i in range(1, n + 1):
            t = i / n
            u = 1.0 - t
            x = u * u * waist_pt.x + 2 * u * t * ctrl.x + t * t * hip_pt.x
            y = u * u * waist_pt.y + 2 * u * t * ctrl.y + t * t * hip_pt.y
            pts.append(Point2D(round(x, 3), round(y, 3)))
        return pts

    @staticmethod
    def _gentle_curve(
        start: Point2D,
        end: Point2D,
        bow_y: float,
        bow_direction: int,
        segments: int = 6,
    ) -> list[Point2D]:
        """Gentle Bézier curve between two points.

        *bow_y* is the magnitude of the curve offset in cm.
        *bow_direction* is -1 for upward bow, +1 for downward bow.
        """
        ctrl = Point2D(
            (start.x + end.x) / 2.0,
            (start.y + end.y) / 2.0 + bow_y * bow_direction,
        )
        pts: list[Point2D] = []
        for i in range(1, segments + 1):
            t = i / segments
            u = 1.0 - t
            x = u * u * start.x + 2 * u * t * ctrl.x + t * t * end.x
            y = u * u * start.y + 2 * u * t * ctrl.y + t * t * end.y
            pts.append(Point2D(round(x, 3), round(y, 3)))
        return pts

    def _make_dart(
        self,
        qtr_waist: float,
        intake: float,
        position_ratio: float,
        dart_length: float,
    ) -> DartGeometry:
        """Create a dart. Apex at waist, legs point downward."""
        dart_x = qtr_waist * position_ratio
        half_intake = intake / 2.0
        if dart_length > 0:
            angle_deg = math.degrees(
                2.0 * math.atan2(half_intake, dart_length),
            )
        else:
            angle_deg = self.MIN_DART_ANGLE
        angle_deg = min(
            max(angle_deg, self.MIN_DART_ANGLE),
            self.MAX_DART_ANGLE,
        )
        return DartGeometry(
            apex=Point2D(dart_x, 0.0),
            angle=angle_deg,
            length=dart_length,
        )

    def _compute_hem_flare(
        self, profile: SkirtMeasurementProfile,
    ) -> float:
        """Compute hem flare width for A-line silhouette."""
        hip_to_hem = profile.desired_length - profile.hip_depth
        return max(0.0, hip_to_hem * self.HEM_FLARE_SCALE)


# ---------------------------------------------------------------------------
# SkirtGarmentSpec — GarmentSpec implementation for skirts
# ---------------------------------------------------------------------------


class SkirtGarmentSpec:
    """GarmentSpec implementation for A-line skirt blocks.

    Provides skirt-specific stress model (hip, waist, hem, side_seam),
    correction strategies (dart angle/length, hem flare), and delegates
    generation to SkirtGenerator.
    """

    GARMENT_TYPE = "skirt"
    MEASUREMENT_FIELDS = ["waist", "hip", "hip_depth", "desired_length"]
    FIT_REGIONS = ["hip", "waist", "hem", "side_seam"]
    DEFAULT_TENSION_THRESHOLDS: dict[str, float] = {
        "hip": 50.0,
        "waist": 45.0,
        "hem": 30.0,
        "side_seam": 40.0,
    }

    # Stress model constants
    FABRIC_STIFFNESS = 1000.0     # Pa
    DART_RELIEF_FACTOR = 0.035    # relief per degree*cm of dart
    EASE_FACTOR = 0.5             # ease contribution weight

    # Correction constants
    WAIST_DART_ANGLE_SCALE = 0.05   # degrees per Pa violation
    WAIST_DART_ANGLE_FLOOR = 0.5    # minimum correction degrees
    WAIST_DART_ANGLE_CAP = 15.0     # maximum correction degrees
    DART_LENGTH_SCALE = 0.01        # cm per Pa violation
    DART_LENGTH_CAP = 5.0           # maximum cm
    HEM_FLARE_SCALE = 0.02          # cm per Pa violation
    HEM_FLARE_CAP = 3.0             # maximum cm

    def __init__(self) -> None:
        self._generator = SkirtGenerator()
        self._last_pieces: list[PatternPiece] | None = None
        self._last_profile: SkirtMeasurementProfile | None = None

    @property
    def garment_type(self) -> str:
        return self.GARMENT_TYPE

    @property
    def measurement_fields(self) -> list[str]:
        return list(self.MEASUREMENT_FIELDS)

    @property
    def fit_regions(self) -> list[str]:
        return list(self.FIT_REGIONS)

    @property
    def tension_thresholds(self) -> dict[str, float]:
        return dict(self.DEFAULT_TENSION_THRESHOLDS)

    def validate_profile(
        self, profile: "MeasurementProfile",
    ) -> list[str]:
        """Validate by constructing a SkirtMeasurementProfile."""
        skirt_profile = self._to_skirt_profile(profile)
        return skirt_profile.validate()

    def generate_initial_pieces(
        self, profile: "MeasurementProfile",
    ) -> list[PatternPiece]:
        """Generate initial skirt pieces from measurements."""
        skirt_profile = self._to_skirt_profile(profile)
        self._last_profile = skirt_profile
        pieces = self._generator.generate(skirt_profile)
        self._last_pieces = pieces
        return pieces

    def compute_stress(
        self,
        pieces: list[PatternPiece],
        profile: "MeasurementProfile",
    ) -> dict[str, float]:
        """Skirt-specific stress model.

        Computes tension for 4 regions:
        - hip: body hip circ vs garment hip circ + ease
        - waist: body waist circ vs garment waist circ + dart relief
        - hem: flare distribution relative to hip-to-hem length
        - side_seam: combined ease/dart relief vs hip-waist diff
        """
        sp = self._to_skirt_profile(profile)
        front = pieces[0]
        back = pieces[1]

        # Garment dimensions from pattern pieces
        front_width = max(p.x for p in front.outline) - min(p.x for p in front.outline)
        back_width = max(p.x for p in back.outline) - min(p.x for p in back.outline)

        garment_hip_circ = (front_width + back_width) * 2.0

        # Dart relief
        all_darts = list(front.darts) + list(back.darts)
        total_dart_relief = sum(
            d.angle * d.length * self.DART_RELIEF_FACTOR
            for d in all_darts
        )

        garment_waist_circ = garment_hip_circ - total_dart_relief * 2.0

        # Hip stress
        hip_stretch = sp.hip / max(garment_hip_circ, 1e-6)
        hip_stress = self.FABRIC_STIFFNESS * max(0.0, hip_stretch - 1.0)

        # Waist stress
        waist_stretch = sp.waist / max(garment_waist_circ, 1e-6)
        waist_stress = self.FABRIC_STIFFNESS * max(0.0, waist_stretch - 1.0)

        # Hem stress — based on flare adequacy
        hip_to_hem = sp.desired_length - sp.hip_depth
        hem_width = (front_width + back_width) * 2.0
        flare_ratio = hem_width / max(garment_hip_circ, 1e-6)
        hem_stress = self.FABRIC_STIFFNESS * max(
            0.0, 1.0 - flare_ratio,
        ) * 0.3

        # Side seam stress
        hip_waist_diff = abs(sp.hip - sp.waist)
        ease_relief = total_dart_relief / max(hip_waist_diff, 1e-6)
        side_stress = self.FABRIC_STIFFNESS * max(
            0.0, 0.5 - ease_relief,
        ) * 0.4

        return {
            "hip": hip_stress,
            "waist": waist_stress,
            "hem": hem_stress,
            "side_seam": side_stress,
        }

    def plan_corrections(
        self,
        fit_issues: list["FitIssue"],
        pieces: list[PatternPiece],
        profile: "MeasurementProfile",
        dampening_factor: float,
    ) -> list["CorrectionStrategy"]:
        """Plan skirt-specific corrections."""
        from agentic_pattern_engine.models import (
            CorrectionStrategy,
            CorrectionType,
            FitIssueType,
        )

        corrections: list[CorrectionStrategy] = []
        for issue in fit_issues:
            violation = issue.violation_magnitude

            if issue.region.value == "waist":
                if issue.issue_type == FitIssueType.EXCESS_TENSION:
                    mag = min(
                        max(
                            violation * self.WAIST_DART_ANGLE_SCALE,
                            self.WAIST_DART_ANGLE_FLOOR,
                        ),
                        self.WAIST_DART_ANGLE_CAP,
                    )
                    corrections.append(CorrectionStrategy(
                        target_region=issue.region,
                        issue_type=issue.issue_type,
                        correction_type=CorrectionType.ADJUST_DART_ANGLE,
                        magnitude=mag * dampening_factor,
                        dampening_factor=dampening_factor,
                    ))
                else:
                    mag = min(
                        violation * self.DART_LENGTH_SCALE,
                        self.DART_LENGTH_CAP,
                    )
                    corrections.append(CorrectionStrategy(
                        target_region=issue.region,
                        issue_type=issue.issue_type,
                        correction_type=CorrectionType.ADJUST_DART_LENGTH,
                        magnitude=mag * dampening_factor,
                        dampening_factor=dampening_factor,
                    ))

            elif issue.region.value == "hem":
                mag = min(
                    violation * self.HEM_FLARE_SCALE,
                    self.HEM_FLARE_CAP,
                )
                corrections.append(CorrectionStrategy(
                    target_region=issue.region,
                    issue_type=issue.issue_type,
                    correction_type=CorrectionType.REDISTRIBUTE_EASE,
                    magnitude=mag * dampening_factor,
                    dampening_factor=dampening_factor,
                ))

            else:
                # hip, side_seam — adjust dart angle
                mag = min(
                    max(
                        violation * self.WAIST_DART_ANGLE_SCALE,
                        self.WAIST_DART_ANGLE_FLOOR,
                    ),
                    self.WAIST_DART_ANGLE_CAP,
                )
                corrections.append(CorrectionStrategy(
                    target_region=issue.region,
                    issue_type=issue.issue_type,
                    correction_type=CorrectionType.ADJUST_DART_ANGLE,
                    magnitude=mag * dampening_factor,
                    dampening_factor=dampening_factor,
                ))

        return corrections

    def apply_corrections(
        self,
        pieces: list[PatternPiece],
        corrections: list["CorrectionStrategy"],
    ) -> list[PatternPiece]:
        """Apply corrections to skirt pieces."""
        import dataclasses
        from agentic_pattern_engine.models import CorrectionType

        updated: list[PatternPiece] = []
        for piece in pieces:
            new_darts = list(piece.darts)
            for corr in corrections:
                if corr.correction_type == CorrectionType.ADJUST_DART_ANGLE:
                    for i, d in enumerate(new_darts):
                        new_darts[i] = DartGeometry(
                            apex=d.apex,
                            angle=d.angle + corr.magnitude,
                            length=d.length,
                        )
                elif corr.correction_type == CorrectionType.ADJUST_DART_LENGTH:
                    for i, d in enumerate(new_darts):
                        new_darts[i] = DartGeometry(
                            apex=d.apex,
                            angle=d.angle,
                            length=max(0.5, d.length - corr.magnitude),
                        )
            updated.append(dataclasses.replace(
                piece, darts=tuple(new_darts),
            ))
        return updated

    def validate_geometry(
        self, pieces: list[PatternPiece],
    ) -> list[str]:
        """Validate skirt geometry."""
        errors: list[str] = []
        for piece in pieces:
            if (
                len(piece.outline) < 2
                or piece.outline[0] != piece.outline[-1]
            ):
                errors.append(
                    f"{piece.label}: outline is not closed"
                )
            if len(piece.darts) < 1:
                errors.append(
                    f"{piece.label}: must have at least one dart"
                )
            if piece.seam_allowance <= 0:
                errors.append(
                    f"{piece.label}: seam_allowance must be > 0"
                )
        return errors

    @staticmethod
    def _to_skirt_profile(
        profile: "MeasurementProfile",
    ) -> SkirtMeasurementProfile:
        """Convert a MeasurementProfile to SkirtMeasurementProfile.

        Uses waist, hip from the profile. hip_depth and desired_length
        are taken from the profile if it's already a
        SkirtMeasurementProfile, otherwise uses defaults.
        """
        if isinstance(profile, SkirtMeasurementProfile):
            return profile
        # Fallback: use profile fields if available
        return SkirtMeasurementProfile(
            waist=getattr(profile, "waist", 73.5),
            hip=getattr(profile, "hip", 98.0),
            hip_depth=getattr(profile, "hip_depth", 20.0),
            desired_length=getattr(profile, "desired_length", 70.0),
        )
