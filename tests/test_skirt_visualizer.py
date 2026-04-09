"""Unit tests for the skirt visualizer."""

from __future__ import annotations

from agentic_pattern_engine.agent_orchestrator import AgentOrchestrator
from agentic_pattern_engine.models import AgentConfig, SkirtMeasurementProfile
from agentic_pattern_engine.skirt_generator import SkirtGarmentSpec
from agentic_pattern_engine.skirt_visualizer import (
    generate_skirt_visualization,
)

_PROFILE = SkirtMeasurementProfile(
    waist=73.5, hip=98.0, hip_depth=20.0, desired_length=70.0,
)


def _run() -> "AuditTrail":
    spec = SkirtGarmentSpec()
    orch = AgentOrchestrator(garment_spec=spec)
    return orch.run(_PROFILE, AgentConfig(iteration_limit=20)).audit_trail


def test_skirt_viz_returns_html() -> None:
    html = generate_skirt_visualization(_PROFILE, _run())
    assert "<!DOCTYPE html>" in html


def test_skirt_viz_contains_three_js() -> None:
    html = generate_skirt_visualization(_PROFILE, _run())
    assert "three.js" in html.lower() or "THREE" in html


def test_skirt_viz_contains_skirt_title() -> None:
    html = generate_skirt_visualization(_PROFILE, _run())
    assert "Skirt Pattern Visualization" in html


def test_skirt_viz_contains_labels() -> None:
    html = generate_skirt_visualization(_PROFILE, _run())
    assert "makeLabel" in html
    assert "'CF'" in html
    assert "'CB'" in html
    assert "'FRONT'" in html
    assert "'BACK'" in html


def test_skirt_viz_contains_iteration_data() -> None:
    html = generate_skirt_visualization(_PROFILE, _run())
    assert '"iterations"' in html
    assert '"garment_vertices"' in html
