"""Body Model Builder — Parametric torso mesh from measurements.

Implements the BodyModelBuilder protocol using a simplified parametric
approach: elliptical cross-sections stacked vertically to form a torso
mesh. This is a POC stand-in for full SMPL/FlexiSMPL integration.
"""

from __future__ import annotations

import math

import numpy as np

from agentic_pattern_engine.models import (
    BodyModel,
    FitRegionVertices,
    MeasurementProfile,
)

# Number of points per elliptical cross-section
NUM_POINTS_PER_SECTION = 20


class ParametricBodyModelBuilder:
    """Build a simplified parametric torso mesh from body measurements."""

    def build(self, profile: MeasurementProfile) -> BodyModel:
        """Map measurements to a 3D torso mesh.

        Creates elliptical cross-sections at hip, waist, bust, and shoulder
        heights, connects them with triangle faces, and assigns fit region
        vertex groups.

        Raises ``ValueError`` if the profile fails validation.
        """
        errors = profile.validate()
        if errors:
            raise ValueError(f"Invalid MeasurementProfile: {'; '.join(errors)}")

        n = NUM_POINTS_PER_SECTION
        torso_len = profile.torso_length

        # Vertical positions: place sections so total span = torso_length.
        # Bottom (hip) at y=0, top (shoulder) at y=torso_len.
        y_hip = 0.0
        y_waist = torso_len * 0.4
        y_bust = torso_len * 0.8
        y_shoulder = torso_len

        # Cross-section definitions: (y_position, circumference, aspect_ratio)
        # aspect_ratio > 1 means wider (x) than deep (z)
        sections = [
            (y_hip, profile.hip, 1.15),          # hip
            (y_waist, profile.waist, 1.10),      # waist
            (y_bust, profile.chest, 1.20),       # bust/chest
            # Shoulder: we need the x-extent (2*a) to equal shoulder_width.
            # We'll handle this specially below.
            None,  # placeholder
        ]

        # For the shoulder section, we need 2*a = shoulder_width.
        # With our parametrisation: a = r * ar, so r = shoulder_width / (2 * ar).
        # The circumference is then derived from r and ar.
        shoulder_ar = 1.40
        shoulder_a = profile.shoulder_width / 2.0
        shoulder_r = shoulder_a / shoulder_ar
        shoulder_b = shoulder_r / shoulder_ar
        # Compute circumference from the polygon that will be generated
        # (perimeter of n-gon inscribed in ellipse with semi-axes a, b)
        shoulder_circ = 0.0
        for i in range(n):
            t0 = 2.0 * math.pi * i / n
            t1 = 2.0 * math.pi * ((i + 1) % n) / n
            dx = shoulder_a * math.cos(t1) - shoulder_a * math.cos(t0)
            dz = shoulder_b * math.sin(t1) - shoulder_b * math.sin(t0)
            shoulder_circ += math.sqrt(dx * dx + dz * dz)

        sections[3] = (y_shoulder, shoulder_circ, shoulder_ar)

        all_vertices: list[np.ndarray] = []
        section_start_indices: list[int] = []

        for y, circumference, aspect in sections:
            section_start_indices.append(len(all_vertices))
            verts = self._ellipse_cross_section(y, circumference, aspect, n)
            all_vertices.extend(verts)

        vertices = np.array(all_vertices, dtype=np.float64)
        faces = self._connect_sections(section_start_indices, n, len(sections))

        fit_regions = self._assign_fit_regions(section_start_indices, n)

        # Store the 5 measurements as a stand-in for SMPL beta params
        shape_params = np.array([
            profile.chest,
            profile.waist,
            profile.hip,
            profile.shoulder_width,
            profile.torso_length,
        ], dtype=np.float64)

        return BodyModel(
            vertices=vertices,
            faces=faces,
            fit_regions=fit_regions,
            smpl_shape_params=shape_params,
            profile=profile,
        )

    def extract_measurements(self, body_model: BodyModel) -> MeasurementProfile:
        """Extract measurements back from mesh geometry.

        Computes circumferences of the cross-section vertices at each
        anatomical level and returns a new MeasurementProfile.
        """
        verts = body_model.vertices
        n = NUM_POINTS_PER_SECTION
        num_sections = len(verts) // n

        # Section ordering: hip(0), waist(1), bust(2), shoulder(3)
        hip_circ = self._compute_circumference(verts, 0 * n, n)
        waist_circ = self._compute_circumference(verts, 1 * n, n)
        chest_circ = self._compute_circumference(verts, 2 * n, n)

        # Shoulder width: distance between leftmost and rightmost shoulder verts
        shoulder_start = 3 * n
        shoulder_verts = verts[shoulder_start: shoulder_start + n]
        shoulder_width = float(np.max(shoulder_verts[:, 0]) - np.min(shoulder_verts[:, 0]))

        # Torso length: vertical distance from bottom to top of mesh
        torso_length = float(np.max(verts[:, 1]) - np.min(verts[:, 1]))

        return MeasurementProfile(
            chest=chest_circ,
            waist=waist_circ,
            hip=hip_circ,
            shoulder_width=shoulder_width,
            torso_length=torso_length,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ellipse_cross_section(
        y: float,
        circumference: float,
        aspect_ratio: float,
        n: int,
    ) -> list[np.ndarray]:
        """Generate *n* points around an ellipse at height *y*.

        Computes semi-axes a, b (with a/b = aspect_ratio²) such that
        the **polygon perimeter** of the n-gon inscribed in the ellipse
        exactly equals the target circumference. This ensures perfect
        round-trip: ``_compute_circumference`` on the resulting vertices
        returns the original circumference.
        """
        ar = aspect_ratio

        # Start with a unit-scale ellipse (r=1) and measure its polygon perimeter.
        # a = r * ar, b = r / ar.  We'll compute perimeter at r=1 then scale.
        unit_perim = 0.0
        for i in range(n):
            t0 = 2.0 * math.pi * i / n
            t1 = 2.0 * math.pi * ((i + 1) % n) / n
            dx = ar * (math.cos(t1) - math.cos(t0))
            dz = (1.0 / ar) * (math.sin(t1) - math.sin(t0))
            unit_perim += math.sqrt(dx * dx + dz * dz)

        # Scale r so that polygon perimeter = circumference
        r = circumference / unit_perim
        a = r * ar   # semi-axis in x
        b = r / ar   # semi-axis in z

        points: list[np.ndarray] = []
        for i in range(n):
            theta = 2.0 * math.pi * i / n
            x = a * math.cos(theta)
            z = b * math.sin(theta)
            points.append(np.array([x, y, z], dtype=np.float64))
        return points

    @staticmethod
    def _connect_sections(
        section_starts: list[int],
        n: int,
        num_sections: int,
    ) -> np.ndarray:
        """Connect adjacent cross-sections with triangle faces."""
        faces: list[list[int]] = []
        for s in range(num_sections - 1):
            base_curr = section_starts[s]
            base_next = section_starts[s + 1]
            for i in range(n):
                i_next = (i + 1) % n
                # Two triangles per quad
                v0 = base_curr + i
                v1 = base_curr + i_next
                v2 = base_next + i
                v3 = base_next + i_next
                faces.append([v0, v1, v2])
                faces.append([v1, v3, v2])
        return np.array(faces, dtype=np.int32)

    @staticmethod
    def _assign_fit_regions(
        section_starts: list[int],
        n: int,
    ) -> FitRegionVertices:
        """Assign vertex indices to named fit regions.

        Section layout: 0=hip, 1=waist, 2=bust/chest, 3=shoulder.
        """
        hip_start = section_starts[0]
        waist_start = section_starts[1]
        bust_start = section_starts[2]
        shoulder_start = section_starts[3]

        # bust: vertices near the chest cross-section
        bust = np.arange(bust_start, bust_start + n, dtype=np.int32)

        # waist: vertices near the waist cross-section
        waist = np.arange(waist_start, waist_start + n, dtype=np.int32)

        # shoulder: vertices near the top (shoulder cross-section)
        shoulder = np.arange(shoulder_start, shoulder_start + n, dtype=np.int32)

        # armhole: vertices on the sides near shoulder height
        # Sides are at θ ≈ 0 (right) and θ ≈ π (left), i.e. indices 0 and n//2
        # Take a few vertices around each side at shoulder and bust levels
        side_indices_per_section = [0, 1, n - 1, n // 2 - 1, n // 2, n // 2 + 1]
        armhole_indices: list[int] = []
        for idx in side_indices_per_section:
            armhole_indices.append(shoulder_start + idx % n)
            armhole_indices.append(bust_start + idx % n)
        armhole = np.array(sorted(set(armhole_indices)), dtype=np.int32)

        # side_seam: vertices along the side edges (θ ≈ 0 and θ ≈ π) across all sections
        side_seam_indices: list[int] = []
        for start in section_starts:
            side_seam_indices.append(start)          # θ = 0 (right side)
            side_seam_indices.append(start + n // 2)  # θ = π (left side)
        side_seam = np.array(sorted(set(side_seam_indices)), dtype=np.int32)

        # center_front: vertices along the front center line (θ ≈ 0, i.e. index 0)
        center_front_indices: list[int] = []
        for start in section_starts:
            center_front_indices.append(start)  # index 0 = front center
        center_front = np.array(sorted(set(center_front_indices)), dtype=np.int32)

        # center_back: vertices along the back center line (θ ≈ π, i.e. index n//2)
        center_back_indices: list[int] = []
        for start in section_starts:
            center_back_indices.append(start + n // 2)
        center_back = np.array(sorted(set(center_back_indices)), dtype=np.int32)

        return FitRegionVertices(
            bust=bust,
            waist=waist,
            shoulder=shoulder,
            armhole=armhole,
            side_seam=side_seam,
            center_front=center_front,
            center_back=center_back,
        )

    @staticmethod
    def _compute_circumference(
        vertices: np.ndarray,
        start_idx: int,
        n: int,
    ) -> float:
        """Compute the perimeter of a cross-section polygon (xz-plane)."""
        total = 0.0
        for i in range(n):
            curr = vertices[start_idx + i]
            nxt = vertices[start_idx + (i + 1) % n]
            dx = nxt[0] - curr[0]
            dz = nxt[2] - curr[2]
            total += math.sqrt(dx * dx + dz * dz)
        return total
