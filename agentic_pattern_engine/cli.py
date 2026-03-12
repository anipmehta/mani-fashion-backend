"""CLI entry point for the Agentic Pattern Engine.

Usage:
    python -m agentic_pattern_engine.cli --chest 91.5 --waist 73.5 --hip 98.0 \
        --shoulder-width 40.0 --torso-length 42.5 --output-dir ./output

    python -m agentic_pattern_engine.cli --profile measurements.json \
        --iteration-limit 10 --output-dir ./output

    # Verbose mode — see every iteration of the self-correction loop
    python -m agentic_pattern_engine.cli --chest 107.0 --waist 68.5 --hip 102.0 \
        --shoulder-width 42.0 --torso-length 44.0 --verbose --output-dir ./output

    # Stress-test with tight thresholds to force multiple correction iterations
    python -m agentic_pattern_engine.cli --chest 107.0 --waist 68.5 --hip 102.0 \
        --shoulder-width 42.0 --torso-length 44.0 --verbose --tight-thresholds \
        --output-dir ./output
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from agentic_pattern_engine.agent_orchestrator import AgentOrchestrator
from agentic_pattern_engine.body_model_builder import ParametricBodyModelBuilder
from agentic_pattern_engine.models import (
    AgentConfig,
    MeasurementProfile,
    TensionThresholds,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="agentic-pattern-engine",
        description="MANI Agentic Pattern Engine — bodice sloper generation with self-correction",
    )
    # Measurement inputs (direct or JSON file)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--profile", type=str, help="Path to JSON measurement file")
    g.add_argument("--chest", type=float, help="Chest circumference (cm)")

    p.add_argument("--waist", type=float, help="Waist circumference (cm)")
    p.add_argument("--hip", type=float, help="Hip circumference (cm)")
    p.add_argument("--shoulder-width", type=float, help="Shoulder width (cm)")
    p.add_argument("--torso-length", type=float, help="Torso length (cm)")

    # Config overrides
    p.add_argument("--iteration-limit", type=int, default=20)
    p.add_argument("--stall-threshold", type=int, default=3)
    p.add_argument("--max-ease-tolerance", type=float, default=2.0)

    # Testing / debug
    p.add_argument("--verbose", "-v", action="store_true",
                    help="Show per-iteration audit trail with fit issues and corrections")
    p.add_argument("--tight-thresholds", action="store_true",
                    help="Use very tight tension thresholds to force multiple correction iterations")

    # Output
    p.add_argument("--output-dir", type=str, default="./output")

    return p.parse_args(argv)


def _load_profile(args: argparse.Namespace) -> MeasurementProfile:
    if args.profile:
        data = json.loads(pathlib.Path(args.profile).read_text())
        return MeasurementProfile(
            chest=data["chest"],
            waist=data["waist"],
            hip=data["hip"],
            shoulder_width=data["shoulder_width"],
            torso_length=data["torso_length"],
        )
    return MeasurementProfile(
        chest=args.chest,
        waist=args.waist,
        hip=args.hip,
        shoulder_width=args.shoulder_width,
        torso_length=args.torso_length,
    )


def _print_audit_trail(result) -> None:
    """Print detailed per-iteration breakdown of the self-correction loop."""
    trail = result.audit_trail
    print("=" * 70)
    print("AUDIT TRAIL — Self-Correction Loop Detail")
    print("=" * 70)

    for entry in trail.entries:
        if entry.iteration == 0:
            print(f"\n--- Iteration 0 (Initial Sloper) ---")
            sloper = entry.sloper
            print(f"  Front bodice: {len(sloper.front_bodice.outline)} outline pts, "
                  f"{len(sloper.front_bodice.darts)} darts")
            print(f"  Back bodice:  {len(sloper.back_bodice.outline)} outline pts, "
                  f"{len(sloper.back_bodice.darts)} darts")
            print(f"  Bust ease: {sloper.bust_ease:.2f} cm, "
                  f"Waist ease: {sloper.waist_ease:.2f} cm")
            continue

        print(f"\n--- Iteration {entry.iteration} ---")
        print(f"  Total stress magnitude: {entry.total_stress_magnitude:.1f} Pa")

        if entry.fit_issues:
            print(f"  Fit issues ({len(entry.fit_issues)}):")
            for issue in entry.fit_issues:
                print(f"    [{issue.region.value}] {issue.issue_type.value}: "
                      f"measured={issue.measured_stress:.0f} Pa, "
                      f"threshold={issue.threshold:.0f} Pa, "
                      f"violation={issue.violation_magnitude:.0f} Pa")
        else:
            print("  Fit issues: NONE — converged!")

        if entry.corrections_applied:
            print(f"  Corrections applied ({len(entry.corrections_applied)}):")
            for corr in entry.corrections_applied:
                print(f"    [{corr.target_region.value}] {corr.correction_type.value}: "
                      f"magnitude={corr.magnitude:.3f}, "
                      f"dampening={corr.dampening_factor:.2f}")

    print()
    print("=" * 70)
    print(f"RESULT: {result.convergence_status.value} "
          f"after {result.total_iterations} iteration(s) "
          f"in {result.elapsed_time_ms:.1f} ms")
    print("=" * 70)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    profile = _load_profile(args)

    # Build thresholds — tight mode uses very low values to force corrections
    if args.tight_thresholds:
        thresholds = TensionThresholds(
            bust=100.0, waist=80.0, shoulder=120.0,
            armhole=110.0, side_seam=90.0,
            center_front=80.0, center_back=80.0,
        )
    else:
        thresholds = TensionThresholds()

    config = AgentConfig(
        iteration_limit=args.iteration_limit,
        stall_threshold=args.stall_threshold,
        max_ease_tolerance=args.max_ease_tolerance,
        tension_thresholds=thresholds,
    )

    print(f"Running Agentic Pattern Engine...")
    print(f"  Chest: {profile.chest} cm")
    print(f"  Waist: {profile.waist} cm")
    print(f"  Hip: {profile.hip} cm")
    print(f"  Shoulder: {profile.shoulder_width} cm")
    print(f"  Torso: {profile.torso_length} cm")
    print(f"  Iteration limit: {config.iteration_limit}")
    if args.tight_thresholds:
        print(f"  Thresholds: TIGHT (bust={thresholds.bust}, waist={thresholds.waist}, ...)")
    print()

    agent = AgentOrchestrator()
    result = agent.run(profile, config)

    # Verbose: show full audit trail
    if args.verbose:
        _print_audit_trail(result)
        print()

    print(f"Status: {result.convergence_status.value}")
    print(f"Iterations: {result.total_iterations}")
    print(f"Time: {result.elapsed_time_ms:.1f} ms")

    if result.error_details:
        print(f"Error: {result.error_details}")
        return 1

    if result.remaining_fit_issues:
        print(f"Remaining issues: {len(result.remaining_fit_issues)}")
        for issue in result.remaining_fit_issues:
            print(f"  - {issue.region.value}: {issue.issue_type.value} "
                  f"({issue.measured_stress:.0f} Pa, threshold {issue.threshold:.0f} Pa)")

    # Write exports
    out = pathlib.Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if result.dxf_bytes:
        dxf_path = out / "pattern.dxf"
        dxf_path.write_bytes(result.dxf_bytes)
        print(f"DXF: {dxf_path}")

    if result.pdf_bytes:
        pdf_path = out / "pattern.pdf"
        pdf_path.write_bytes(result.pdf_bytes)
        print(f"PDF: {pdf_path}")

    # Export 3D body model as OBJ for viewing in Blender / MeshLab
    try:
        builder = ParametricBodyModelBuilder()
        body_model = builder.build(profile)
        obj_str = builder.export_obj(body_model)
        obj_path = out / "body_model.obj"
        obj_path.write_text(obj_str)
        print(f"3D Model (OBJ): {obj_path}")
    except Exception as e:
        print(f"OBJ export skipped: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
