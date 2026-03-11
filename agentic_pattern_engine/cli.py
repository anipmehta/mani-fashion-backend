"""CLI entry point for the Agentic Pattern Engine.

Usage:
    python -m agentic_pattern_engine.cli --chest 91.5 --waist 73.5 --hip 98.0 \
        --shoulder-width 40.0 --torso-length 42.5 --output-dir ./output

    python -m agentic_pattern_engine.cli --profile measurements.json \
        --iteration-limit 10 --output-dir ./output
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from agentic_pattern_engine.agent_orchestrator import AgentOrchestrator
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


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    profile = _load_profile(args)

    config = AgentConfig(
        iteration_limit=args.iteration_limit,
        stall_threshold=args.stall_threshold,
        max_ease_tolerance=args.max_ease_tolerance,
    )

    print(f"Running Agentic Pattern Engine...")
    print(f"  Chest: {profile.chest} cm")
    print(f"  Waist: {profile.waist} cm")
    print(f"  Hip: {profile.hip} cm")
    print(f"  Shoulder: {profile.shoulder_width} cm")
    print(f"  Torso: {profile.torso_length} cm")
    print(f"  Iteration limit: {config.iteration_limit}")
    print()

    agent = AgentOrchestrator()
    result = agent.run(profile, config)

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

    return 0


if __name__ == "__main__":
    sys.exit(main())
