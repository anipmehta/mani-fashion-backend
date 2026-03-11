"""Property tests for the Audit Trail Recorder.

Property 11 from the design document.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings

from agentic_pattern_engine.audit_trail import AuditTrailRecorder
from agentic_pattern_engine.models import AuditEntry, TensionMap
from agentic_pattern_engine.sloper_generator import ParsonsSloperGenerator
from tests.conftest import measurement_profiles

import numpy as np

_generator = ParsonsSloperGenerator()


# Feature: agentic-pattern-engine, Property 11: Audit trail integrity
@given(profile=measurement_profiles())
@settings(max_examples=50)
def test_audit_trail_integrity(profile):
    """For any completed agent run simulation:
    - first entry is iteration 0 with initial sloper and None tension_map
    - entries strictly ordered
    - count equals total_iterations + 1
    - entries after 0 have non-null tension_map
    """
    sloper = _generator.generate(profile)
    recorder = AuditTrailRecorder()

    # Record iteration 0
    recorder.record(AuditEntry(
        iteration=0,
        sloper=sloper,
        tension_map=None,
        fit_issues=[],
        corrections_applied=[],
        total_stress_magnitude=0.0,
    ))

    # Simulate a few iterations
    n_iters = 3
    for i in range(1, n_iters + 1):
        tm = TensionMap(
            vertex_stresses=np.array([100.0 * i], dtype=np.float64),
            collision_vertices=np.array([], dtype=np.int32),
        )
        recorder.record(AuditEntry(
            iteration=i,
            sloper=sloper,
            tension_map=tm,
            fit_issues=[],
            corrections_applied=[],
            total_stress_magnitude=float(100.0 * i),
        ))

    trail = recorder.get_trail()

    # (a) First entry is iteration 0 with None tension_map
    assert trail.entries[0].iteration == 0
    assert trail.entries[0].tension_map is None
    assert trail.entries[0].fit_issues == []
    assert trail.entries[0].corrections_applied == []

    # (b) Entries strictly ordered
    for j in range(len(trail.entries) - 1):
        assert trail.entries[j].iteration < trail.entries[j + 1].iteration

    # (c) Count equals total_iterations + 1
    assert len(trail.entries) == n_iters + 1
    assert trail.iteration_count == n_iters

    # (d) Entries after 0 have non-null tension_map
    for entry in trail.entries[1:]:
        assert entry.tension_map is not None


def test_audit_trail_rejects_out_of_order():
    """Recording out-of-order entries must raise ValueError."""
    recorder = AuditTrailRecorder()
    sloper = _generator.generate(
        __import__("tests.conftest", fromlist=["SAMPLE_PROFILES"]).SAMPLE_PROFILES["medium"]
    )
    recorder.record(AuditEntry(
        iteration=0, sloper=sloper, tension_map=None,
        fit_issues=[], corrections_applied=[], total_stress_magnitude=0.0,
    ))
    with pytest.raises(ValueError):
        recorder.record(AuditEntry(
            iteration=0, sloper=sloper, tension_map=None,
            fit_issues=[], corrections_applied=[], total_stress_magnitude=0.0,
        ))
