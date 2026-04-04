"""Property-based tests for the Simulation Engine.

Tests Properties 6 and 7 from the design document.
"""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings

from agentic_pattern_engine.body_model_builder import ParametricBodyModelBuilder
from agentic_pattern_engine.simulation_engine import MassSpringSimulationEngine
from agentic_pattern_engine.sloper_generator import ParsonsSloperGenerator

from tests.conftest import measurement_profiles


# Feature: agentic-pattern-engine, Property 6: Simulation output completeness
# **Validates: Requirements 3.1, 3.3, 3.4**
@given(profile=measurement_profiles())
@settings(max_examples=50)
def test_simulation_output_completeness(profile):
    """For any valid BodiceSloper and BodyModel, simulate must return
    TensionMap with non-negative per-vertex stresses, collision_vertices
    array, and positive simulation_time_ms."""
    gen = ParsonsSloperGenerator()
    builder = ParametricBodyModelBuilder()
    sim = MassSpringSimulationEngine()

    sloper = gen.generate(profile)
    body_model = builder.build(profile)
    result = sim.simulate(sloper, body_model)

    # TensionMap has vertices with non-negative stresses
    assert len(result.tension_map.vertex_stresses) > 0
    assert np.all(result.tension_map.vertex_stresses >= 0)
    # collision_vertices is an array (possibly empty)
    assert isinstance(result.tension_map.collision_vertices, np.ndarray)
    # positive simulation time
    assert result.simulation_time_ms > 0
    # simulation solver converged
    assert result.converged is True


# Feature: agentic-pattern-engine, Property 7: Simulation determinism
# **Validates: Requirements 3.5**
@given(profile=measurement_profiles())
@settings(max_examples=50)
def test_simulation_determinism(profile):
    """For any valid BodiceSloper and BodyModel, two simulation runs must
    produce TensionMaps differing by <= 1% relative tolerance."""
    gen = ParsonsSloperGenerator()
    builder = ParametricBodyModelBuilder()
    sim = MassSpringSimulationEngine()

    sloper = gen.generate(profile)
    body_model = builder.build(profile)
    r1 = sim.simulate(sloper, body_model)
    r2 = sim.simulate(sloper, body_model)

    # Stress values should be identical (deterministic, no randomness)
    np.testing.assert_allclose(
        r1.tension_map.vertex_stresses,
        r2.tension_map.vertex_stresses,
        rtol=0.01,  # 1% tolerance
    )
    # Collision vertices should be identical
    np.testing.assert_array_equal(
        r1.tension_map.collision_vertices,
        r2.tension_map.collision_vertices,
    )


# ---------------------------------------------------------------------------
# PR 3: stress_fn callable injection tests
# ---------------------------------------------------------------------------

from tests.conftest import SAMPLE_PROFILES


def test_simulation_engine_stress_fn_callable_used() -> None:
    """When stress_fn is provided, simulate uses it instead of
    _compute_regional_stresses."""
    profile = SAMPLE_PROFILES["medium"]
    gen = ParsonsSloperGenerator()
    builder = ParametricBodyModelBuilder()
    sim = MassSpringSimulationEngine()

    sloper = gen.generate(profile)
    body_model = builder.build(profile)

    custom_stresses = {"bust": 99.0, "waist": 88.0}

    def fake_stress_fn(pieces, prof):
        return custom_stresses

    result = sim.simulate(sloper, body_model, stress_fn=fake_stress_fn)
    assert result.tension_map.regional_stresses == custom_stresses


def test_simulation_engine_stress_fn_none_uses_default() -> None:
    """When stress_fn is None, simulate uses the built-in
    _compute_regional_stresses (bodice default)."""
    profile = SAMPLE_PROFILES["medium"]
    gen = ParsonsSloperGenerator()
    builder = ParametricBodyModelBuilder()
    sim = MassSpringSimulationEngine()

    sloper = gen.generate(profile)
    body_model = builder.build(profile)

    result = sim.simulate(sloper, body_model, stress_fn=None)
    regional = result.tension_map.regional_stresses
    assert regional is not None
    assert "bust" in regional
    assert "waist" in regional


def test_simulation_engine_stress_fn_receives_pieces() -> None:
    """stress_fn receives the front/back pieces from the sloper."""
    profile = SAMPLE_PROFILES["medium"]
    gen = ParsonsSloperGenerator()
    builder = ParametricBodyModelBuilder()
    sim = MassSpringSimulationEngine()

    sloper = gen.generate(profile)
    body_model = builder.build(profile)

    captured = {}

    def spy_stress_fn(pieces, prof):
        captured["pieces"] = pieces
        captured["profile"] = prof
        return {"bust": 0.0}

    sim.simulate(sloper, body_model, stress_fn=spy_stress_fn)
    assert len(captured["pieces"]) == 2
    assert captured["pieces"][0].piece_id == "front_bodice"
    assert captured["profile"] is profile
