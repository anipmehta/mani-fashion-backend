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
    DartGeometry,
    Line2D,
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
