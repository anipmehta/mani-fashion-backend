"""Simulation Engine — CPU-based analytical stress estimation.

Implements the SimulationEngine protocol using an analytical stress
estimation approach. For the POC, instead of a full GPU-accelerated
mass-spring time-stepping simulation, we compute per-vertex stress
by comparing the garment dimensions (from the sloper) against the
body dimensions (from the body model) and distributing stress to
vertices based on their fit region membership.

The simulation is fully deterministic: same inputs always produce
the same outputs.
"""

from __future__ import annotations

import math
import time

import numpy as np

from agentic_pattern_engine.models import (
    BodyModel,
    BodiceSloper,
    FitRegion,
    MeasurementProfile,
    Point2D,
    SimulationResult,
    TensionMap,
)

# Default fabric stiffness in Pascals
DEFAULT_FABRIC_STIFFNESS = 1000.0


class MassSpringSimulationEngine:
    """Analytical stress estimation engine for bodice slopers.

    Maps 2D pattern pieces onto the 3D body model surface and computes
    per-vertex stress based on the stretch ratio between garment
    dimensions and body dimensions.
    """

    def __init__(self, fabric_stiffness: float = DEFAULT_FABRIC_STIFFNESS) -> None:
        self.fabric_stiffness = fabric_stiffness

    def simulate(
        self,
        sloper: BodiceSloper,
        body_model: BodyModel,
    ) -> SimulationResult:
        """Run analytical stress estimation on the sloper draped over body_model.

        Returns a SimulationResult with per-vertex stress values and
        collision data. The simulation is deterministic.
        """
        start = time.perf_counter()

        # 1. Create garment mesh vertices by mapping pattern to body
        garment_vertices = self._map_pattern_to_body(sloper, body_model)

        # 2. Compute per-vertex stress
        stresses = self._compute_stresses(sloper, body_model, garment_vertices)

        # 3. Detect collisions
        collisions = self._detect_collisions(garment_vertices, body_model)

        elapsed = (time.perf_counter() - start) * 1000.0

        tension_map = TensionMap(
            vertex_stresses=stresses,
            collision_vertices=collisions,
            regional_stresses=self._compute_regional_stresses(sloper, body_model.profile),
        )
        return SimulationResult(
            tension_map=tension_map,
            simulation_time_ms=elapsed,
            converged=True,
        )

    # ------------------------------------------------------------------
    # Pattern-to-body mapping
    # ------------------------------------------------------------------

    def _map_pattern_to_body(
        self,
        sloper: BodiceSloper,
        body_model: BodyModel,
    ) -> np.ndarray:
        """Map 2D pattern piece outlines onto the 3D body surface.

        Samples points from the pattern pieces and projects them onto
        the nearest body model vertices, creating a garment mesh that
        conforms to the body surface.

        Returns an (N, 3) array of garment vertex positions.
        """
        body_verts = body_model.vertices
        n_body = len(body_verts)

        # Collect 2D pattern points from both pieces
        pattern_points_2d: list[tuple[float, float]] = []
        for piece in (sloper.front_bodice, sloper.back_bodice):
            for pt in piece.outline[:-1]:  # skip closing duplicate
                pattern_points_2d.append((pt.x, pt.y))
            # Also sample dart apex positions
            for dart in piece.darts:
                pattern_points_2d.append((dart.apex.x, dart.apex.y))
            # Sample notch marks
            for notch in piece.notch_marks:
                pattern_points_2d.append((notch.x, notch.y))

        if not pattern_points_2d:
            # Fallback: use body vertices directly
            return body_verts.copy()

        # Normalize 2D pattern coordinates to [0, 1] range
        pts = np.array(pattern_points_2d, dtype=np.float64)
        x_min, y_min = pts.min(axis=0)
        x_max, y_max = pts.max(axis=0)
        x_range = max(x_max - x_min, 1e-6)
        y_range = max(y_max - y_min, 1e-6)

        # Map normalized pattern coords to body surface
        # x -> body x (width), y -> body y (height)
        body_x_min = float(body_verts[:, 0].min())
        body_x_max = float(body_verts[:, 0].max())
        body_y_min = float(body_verts[:, 1].min())
        body_y_max = float(body_verts[:, 1].max())
        body_x_range = max(body_x_max - body_x_min, 1e-6)
        body_y_range = max(body_y_max - body_y_min, 1e-6)

        garment_vertices: list[np.ndarray] = []
        for px, py in pattern_points_2d:
            # Normalize to [0, 1]
            nx = (px - x_min) / x_range
            ny = (py - y_min) / y_range

            # Map to body coordinate range
            target_x = body_x_min + nx * body_x_range
            target_y = body_y_min + ny * body_y_range

            # Find nearest body vertex by x and y
            distances = (body_verts[:, 0] - target_x) ** 2 + (body_verts[:, 1] - target_y) ** 2
            nearest_idx = int(np.argmin(distances))
            # Place garment vertex slightly outside body surface
            body_pt = body_verts[nearest_idx].copy()
            # Offset outward along the radial direction (xz plane)
            radial = np.array([body_pt[0], 0.0, body_pt[2]])
            radial_norm = np.linalg.norm(radial)
            if radial_norm > 1e-6:
                body_pt[:] = body_pt + (radial / radial_norm) * 0.5  # 5mm offset
            garment_vertices.append(body_pt)

        return np.array(garment_vertices, dtype=np.float64)

    # ------------------------------------------------------------------
    # Stress computation
    # ------------------------------------------------------------------

    def _compute_stresses(
        self,
        sloper: BodiceSloper,
        body_model: BodyModel,
        garment_vertices: np.ndarray,
    ) -> np.ndarray:
        """Compute per-vertex stress based on stretch between garment and body.

        The key insight: compare the "required" garment dimensions from
        the body model against the "available" garment dimensions from
        the sloper. Where required > available → tension. Where
        required < available → low stress.

        Stress is distributed to garment vertices based on their
        proximity to each fit region.
        """
        n_garment = len(garment_vertices)
        stresses = np.zeros(n_garment, dtype=np.float64)

        profile = body_model.profile

        # --- Compute regional stretch ratios ---
        # Each region has a "body dimension" and a "garment dimension"
        # stretch_ratio = body_dimension / garment_dimension
        # stress = fabric_stiffness * |stretch_ratio - 1.0|

        region_stresses = self._compute_regional_stresses(sloper, profile)

        # --- Distribute regional stress to garment vertices ---
        # Map each garment vertex to the closest body region and assign
        # the corresponding regional stress
        body_verts = body_model.vertices
        fit_regions = body_model.fit_regions

        # Build a mapping: body vertex index -> region name -> stress
        vertex_region_map = self._build_vertex_region_map(fit_regions)

        for i, gv in enumerate(garment_vertices):
            # Find nearest body vertex
            distances = np.sum((body_verts - gv) ** 2, axis=1)
            nearest_body_idx = int(np.argmin(distances))

            # Look up which region this body vertex belongs to
            region_name = vertex_region_map.get(nearest_body_idx)
            if region_name and region_name in region_stresses:
                stresses[i] = region_stresses[region_name]
            # Unmapped vertices get zero stress — no phantom tension

        return stresses

    def _compute_regional_stresses(
        self,
        sloper: BodiceSloper,
        profile: MeasurementProfile,
    ) -> dict[str, float]:
        """Compute stress for each fit region based on garment vs body dimensions.

        The simulation accounts for:
        - Pattern outline dimensions (width/height)
        - Ease values (bust_ease, waist_ease)
        - Dart geometry: wider dart angles and longer darts provide more
          fabric relief, reducing stress.
        - 3D shaping difficulty: a flat pattern must conform to a curved
          body.  The bust-waist differential creates inherent tension
          even when the garment has enough circumference, because the
          fabric must curve around the bust prominence.  Darts are the
          primary mechanism to relieve this shaping stress.

        Returns a dict mapping region name to stress in Pascals.
        """
        chest = profile.chest
        waist = profile.waist
        shoulder_width = profile.shoulder_width

        bust_ease = sloper.bust_ease
        waist_ease = sloper.waist_ease

        # Garment dimensions (from sloper pattern)
        front_outline = sloper.front_bodice.outline
        back_outline = sloper.back_bodice.outline

        front_width = self._pattern_width(front_outline)
        back_width = self._pattern_width(back_outline)
        front_height = self._pattern_height(front_outline)

        # Full garment circumference at bust level, including ease
        garment_bust_circ = (front_width + back_width) * 2.0 + bust_ease
        # Full garment circumference at waist level
        garment_waist_circ = (front_width + back_width) * 2.0 + waist_ease

        # --- Dart relief computation ---
        front_darts = sloper.front_bodice.darts
        back_darts = sloper.back_bodice.darts

        # Front dart[0] = bust dart, dart[1+] = waist darts
        front_bust_relief = (
            front_darts[0].angle * front_darts[0].length * 0.035
            if front_darts else 0.0
        )
        front_waist_relief = sum(
            d.angle * d.length * 0.035
            for d in front_darts[1:]
        )
        back_dart_relief = sum(
            d.angle * d.length * 0.035
            for d in back_darts
        )

        total_bust_dart_relief = front_bust_relief + back_dart_relief * 0.3
        total_waist_dart_relief = front_waist_relief + back_dart_relief * 0.7

        # Effective garment circumferences after dart relief
        effective_bust_circ = garment_bust_circ + total_bust_dart_relief * 1.2
        effective_waist_circ = garment_waist_circ + total_waist_dart_relief * 0.8 + waist_ease * 0.5

        # --- 3D shaping difficulty ---
        # A flat pattern wrapped around a 3D body with bust-waist
        # differential creates inherent tension.  The larger the
        # differential, the more the fabric must stretch/compress to
        # conform.  Darts relieve this by removing wedges of fabric.
        bust_waist_diff = abs(chest - waist)
        shaping_difficulty = bust_waist_diff / max(chest, 1.0)

        # --- Bust region ---
        bust_stretch = chest / max(effective_bust_circ, 1e-6)
        bust_stress_raw = self.fabric_stiffness * max(0.0, bust_stretch - 1.0)
        # Shaping stress: the bust prominence creates tension even when
        # the garment has enough circumference.  Darts relieve this.
        bust_shaping = self.fabric_stiffness * shaping_difficulty * 0.6
        bust_dart_relief_frac = min(total_bust_dart_relief / max(chest * 0.08, 1.0), 1.0)
        bust_shaping *= max(0.0, 1.0 - bust_dart_relief_frac)
        bust_stress = bust_stress_raw + bust_shaping

        # --- Waist region ---
        waist_stretch = waist / max(effective_waist_circ, 1e-6)
        waist_stress_raw = self.fabric_stiffness * max(0.0, waist_stretch - 1.0)
        # Waist shaping: the waist must be taken in relative to bust.
        waist_shaping = self.fabric_stiffness * shaping_difficulty * 0.5
        waist_dart_relief_frac = min(total_waist_dart_relief / max(waist * 0.06, 1.0), 1.0)
        waist_ease_relief_frac = min(waist_ease / max(bust_waist_diff * 0.3, 1.0), 1.0)
        waist_shaping *= max(0.0, 1.0 - waist_dart_relief_frac - waist_ease_relief_frac * 0.5)
        waist_stress = waist_stress_raw + waist_shaping

        # --- Shoulder region ---
        garment_shoulder = front_width + back_width
        shoulder_stretch = shoulder_width / max(garment_shoulder, 1e-6)
        shoulder_stress = self.fabric_stiffness * max(0.0, shoulder_stretch - 1.0) * 0.8

        # --- Armhole region ---
        bust_shoulder_ratio = chest / max(shoulder_width * 2.0, 1e-6)
        armhole_shaping = self.fabric_stiffness * max(0.0, bust_shoulder_ratio - 0.9) * 0.5
        armhole_dart_factor = max(0.0, 1.0 - total_bust_dart_relief / max(chest * 0.06, 1e-6))
        armhole_stress = armhole_shaping * armhole_dart_factor

        # --- Side seam region ---
        ease_relief = (bust_ease + waist_ease) / max(chest, 1e-6)
        dart_side_relief = (total_bust_dart_relief + total_waist_dart_relief) / max(chest, 1e-6) * 1.5
        side_seam_stress = self.fabric_stiffness * max(0.0, shaping_difficulty - ease_relief - dart_side_relief) * 0.4

        # --- Center front ---
        cf_dart_factor = max(0.0, 1.0 - total_bust_dart_relief / max(chest * 0.05, 1e-6))
        cf_ease_factor = max(0.0, 1.0 - bust_ease / max(chest * 0.12, 1e-6))
        center_front_stress = (bust_stress_raw + bust_shaping * 0.3) * 0.4 * cf_dart_factor * cf_ease_factor

        # --- Center back ---
        cb_dart_factor = max(0.0, 1.0 - back_dart_relief / max(chest * 0.08, 1e-6))
        center_back_stress = (shoulder_stress * 0.3 + self.fabric_stiffness * abs(
            back_dart_relief / max(front_height, 1e-6)
        ) * 0.2) * cb_dart_factor

        return {
            "bust": bust_stress,
            "waist": waist_stress,
            "shoulder": shoulder_stress,
            "armhole": armhole_stress,
            "side_seam": side_seam_stress,
            "center_front": center_front_stress,
            "center_back": center_back_stress,
        }

    @staticmethod
    def _build_vertex_region_map(
        fit_regions: "FitRegionVertices",
    ) -> dict[int, str]:
        """Build a mapping from body vertex index to region name.

        If a vertex belongs to multiple regions, the first match wins
        (priority: bust > waist > shoulder > armhole > side_seam >
        center_front > center_back).
        """
        region_map: dict[int, str] = {}
        # Process in reverse priority so higher-priority overwrites
        for region_name in reversed([
            "bust", "waist", "shoulder", "armhole",
            "side_seam", "center_front", "center_back",
        ]):
            indices = getattr(fit_regions, region_name)
            for idx in indices:
                region_map[int(idx)] = region_name
        return region_map

    @staticmethod
    def _pattern_width(outline: tuple[Point2D, ...]) -> float:
        """Compute the width (x-extent) of a pattern piece outline."""
        if not outline:
            return 0.0
        xs = [p.x for p in outline]
        return max(xs) - min(xs)

    @staticmethod
    def _pattern_height(outline: tuple[Point2D, ...]) -> float:
        """Compute the height (y-extent) of a pattern piece outline."""
        if not outline:
            return 0.0
        ys = [p.y for p in outline]
        return max(ys) - min(ys)

    # ------------------------------------------------------------------
    # Collision detection
    # ------------------------------------------------------------------

    def _detect_collisions(
        self,
        garment_vertices: np.ndarray,
        body_model: BodyModel,
    ) -> np.ndarray:
        """Detect garment vertices that penetrate the body model.

        A garment vertex is considered colliding if it is closer to the
        body centroid than the nearest body surface vertex (i.e., it is
        "inside" the body).

        Returns an array of garment vertex indices that are in collision.
        """
        body_verts = body_model.vertices

        # Compute body centroid (approximate center of mass)
        centroid = body_verts.mean(axis=0)

        collision_indices: list[int] = []
        for i, gv in enumerate(garment_vertices):
            # Find nearest body vertex
            distances = np.sum((body_verts - gv) ** 2, axis=1)
            nearest_idx = int(np.argmin(distances))
            nearest_body = body_verts[nearest_idx]

            # Compare distance to centroid: if garment vertex is closer
            # to centroid than the body surface vertex, it's inside
            gv_dist = float(np.linalg.norm(gv - centroid))
            body_dist = float(np.linalg.norm(nearest_body - centroid))

            if gv_dist < body_dist - 0.1:  # 1mm tolerance
                collision_indices.append(i)

        return np.array(collision_indices, dtype=np.int32)
