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
from agentic_pattern_engine.html_visualizer import generate_visualization
from agentic_pattern_engine.models import (
    AgentConfig,
    MeasurementProfile,
    TensionThresholds,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="agentic-pattern-engine",
        description=(
            "MANI Agentic Pattern Engine — garment pattern "
            "generation with self-correction"
        ),
    )

    # Garment type
    p.add_argument(
        "--garment", type=str, default="bodice",
        choices=["bodice", "skirt"],
        help="Garment type: bodice (default) or skirt",
    )

    # Grading mode
    p.add_argument(
        "--grade", type=str, default=None, metavar="PATTERN_FILE",
        help="Path to a DXF or SVG pattern file to re-grade",
    )

    # Measurement inputs (direct or JSON file)
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument("--profile", type=str, help="Path to JSON measurement file")
    g.add_argument(
        "--chest", type=float,
        help="Chest circumference (cm) — bodice primary measurement",
    )
    g.add_argument(
        "--waist-primary", type=float, dest="waist_primary",
        help="Waist circumference (cm) — skirt primary measurement "
             "(use with --garment skirt)",
    )
    g.add_argument("--scan", type=str, help="Path to JSON scan file")

    p.add_argument("--waist", type=float, help="Waist circumference (cm)")
    p.add_argument("--hip", type=float, help="Hip circumference (cm)")
    p.add_argument("--shoulder-width", type=float, help="Shoulder width (cm)")
    p.add_argument("--torso-length", type=float, help="Torso length (cm)")

    # Skirt-specific measurements
    p.add_argument("--hip-depth", type=float, help="Hip depth (cm) — skirt only")
    p.add_argument("--desired-length", type=float, help="Desired length (cm) — skirt only")

    # Config overrides
    p.add_argument("--iteration-limit", type=int, default=20)
    p.add_argument("--stall-threshold", type=int, default=5)
    p.add_argument("--max-ease-tolerance", type=float, default=2.0)

    # Testing / debug
    p.add_argument("--verbose", "-v", action="store_true",
                    help="Show per-iteration audit trail with fit issues and corrections")
    p.add_argument("--tight-thresholds", action="store_true",
                    help="Use very tight tension thresholds to force multiple correction iterations")
    p.add_argument("--dump-iterations", action="store_true",
                    help="Export pattern OBJ for every iteration (iterations/ subfolder)")

    # Output
    p.add_argument("--output-dir", type=str, default="./output")

    ns = p.parse_args(argv)
    # Track whether --garment was explicitly provided by the user.
    # argparse doesn't expose this directly, so we check the raw argv.
    effective_argv = argv if argv is not None else sys.argv[1:]
    ns._garment_explicit = any(
        a == "--garment" or a.startswith("--garment=")
        for a in effective_argv
    )

    # When not grading, require at least one measurement source
    if not ns.grade:
        has_measurements = (
            ns.profile or ns.chest or ns.waist_primary
            or getattr(ns, "scan", None)
        )
        if not has_measurements:
            p.error(
                "one of --profile, --chest, --waist-primary, "
                "--scan is required (or use --grade)"
            )

    return ns


def _load_scan_profile(
    args: argparse.Namespace,
) -> tuple[MeasurementProfile | object, str]:
    """Load a measurement profile from a scanner JSON file.

    Reads the file, parses via AdapterRegistry, prints scan info,
    determines garment type from hints (or --garment override),
    and converts to the appropriate profile.
    """
    from agentic_pattern_engine.models import SkirtMeasurementProfile
    from agentic_pattern_engine.scanner import (
        AdapterRegistry,
        GarmentHint,
        scan_result_to_bodice_profile,
        scan_result_to_skirt_profile,
    )

    try:
        raw = pathlib.Path(args.scan).read_text()
    except FileNotFoundError:
        print(f"Error: scan file not found: {args.scan}")
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in scan file: {exc}")
        sys.exit(1)

    try:
        registry = AdapterRegistry()
        scan_result = registry.parse(data)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    print(f"Scanner: {scan_result.scanner_type}")
    print(f"Source unit: {scan_result.source_unit}")
    print(f"Measurements: {scan_result.measurements}")

    # Determine garment type
    garment_explicitly_set = getattr(args, "_garment_explicit", False)
    hints = scan_result.garment_hints

    if garment_explicitly_set:
        garment_type: str = args.garment
    elif hints == GarmentHint.BOTH:
        garment_type = "bodice"
    elif hints == GarmentHint.BODICE_ONLY:
        garment_type = "bodice"
    elif hints == GarmentHint.SKIRT_ONLY:
        garment_type = "skirt"
    else:
        print(
            "Error: scan has insufficient measurements for "
            "any garment type"
        )
        sys.exit(1)

    try:
        if garment_type == "skirt":
            profile = scan_result_to_skirt_profile(scan_result)
        else:
            profile = scan_result_to_bodice_profile(scan_result)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    return profile, garment_type


def _load_profile(
    args: argparse.Namespace,
) -> tuple[MeasurementProfile | object, str]:
    """Load measurement profile based on garment type.

    Returns (profile, garment_type) where profile is
    MeasurementProfile for bodice or SkirtMeasurementProfile
    for skirt.  When --profile is used, auto-detects garment type
    from the JSON 'garment_type' field if present.
    """
    from agentic_pattern_engine.models import SkirtMeasurementProfile

    if getattr(args, "scan", None):
        return _load_scan_profile(args)

    if args.profile:
        data = json.loads(pathlib.Path(args.profile).read_text())
        garment = data.get("garment_type", args.garment)

        if garment == "skirt":
            return SkirtMeasurementProfile(
                waist=data["waist"],
                hip=data["hip"],
                hip_depth=data["hip_depth"],
                desired_length=data["desired_length"],
            ), "skirt"

        return MeasurementProfile(
            chest=data["chest"],
            waist=data["waist"],
            hip=data["hip"],
            shoulder_width=data["shoulder_width"],
            torso_length=data["torso_length"],
        ), "bodice"

    if args.garment == "skirt":
        waist = args.waist_primary or args.waist
        if not waist or not args.hip:
            print("Error: --waist-primary and --hip are required for skirt")
            sys.exit(1)
        if not args.hip_depth or not args.desired_length:
            print(
                "Error: --hip-depth and --desired-length "
                "are required for skirt"
            )
            sys.exit(1)
        return SkirtMeasurementProfile(
            waist=waist,
            hip=args.hip,
            hip_depth=args.hip_depth,
            desired_length=args.desired_length,
        ), "skirt"

    return MeasurementProfile(
        chest=args.chest,
        waist=args.waist,
        hip=args.hip,
        shoulder_width=args.shoulder_width,
        torso_length=args.torso_length,
    ), "bodice"


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


def _run_grade_mode(args: argparse.Namespace) -> int:
    """Execute --grade mode: parse pattern, grade to target, export."""
    from agentic_pattern_engine.grading_engine import GradingEngine
    from agentic_pattern_engine.pattern_parser import (
        SUPPORTED_FORMATS,
        PatternParser,
    )

    parser = PatternParser()
    parse_result = parser.parse(args.grade)

    if parse_result.errors:
        for err in parse_result.errors:
            print(f"Error: {err}")
        if "Unrecognized format" in parse_result.errors[0]:
            print(
                f"Supported formats: "
                f"{', '.join(sorted(SUPPORTED_FORMATS))}"
            )
        return 1

    # Require target measurements
    has_target = (
        args.profile or args.chest or args.waist_primary
        or getattr(args, "scan", None)
    )
    if not has_target:
        print(
            "Error: target measurements required for grading. "
            "Use --chest/--waist/etc. or --profile."
        )
        return 1

    target_profile, garment_type = _load_profile(args)

    # Use detected garment type from pattern if not explicit
    garment_explicit = getattr(args, "_garment_explicit", False)
    if not garment_explicit and parse_result.garment_type:
        garment_type = parse_result.garment_type

    # Build source profile from parsed pattern metadata
    # For DXF round-trip, the exporter stores profile in metadata
    source_profile = target_profile  # fallback

    # Build orchestrator with appropriate garment spec
    garment_spec = None
    if garment_type == "skirt":
        from agentic_pattern_engine.skirt_generator import (
            SkirtGarmentSpec,
        )
        garment_spec = SkirtGarmentSpec()

    orchestrator = AgentOrchestrator(garment_spec=garment_spec)
    engine = GradingEngine(orchestrator=orchestrator)

    print(f"Grading pattern: {args.grade}")
    print(f"  Source format: {parse_result.source_format}")
    print(f"  Pieces found: {len(parse_result.pieces)}")
    print(f"  Garment type: {garment_type}")
    print()

    result = engine.grade(
        parse_result.pieces,
        source_profile,
        target_profile,
        garment_type,
    )

    # Print grading summary
    _print_grading_summary(result, garment_type, target_profile)

    # Print warnings
    for warning in result.warnings:
        print(f"Warning: {warning}")

    # Verbose: print audit trail from self-correction
    if args.verbose and result.run_result is not None:
        _print_audit_trail(result.run_result)

    # Export re-graded pattern
    out = pathlib.Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if result.run_result and result.run_result.dxf_bytes:
        dxf_path = out / "graded_pattern.dxf"
        dxf_path.write_bytes(result.run_result.dxf_bytes)
        print(f"DXF: {dxf_path}")

    if result.run_result and result.run_result.pdf_bytes:
        pdf_path = out / "graded_pattern.pdf"
        pdf_path.write_bytes(result.run_result.pdf_bytes)
        print(f"PDF: {pdf_path}")

    return 0


def _print_grading_summary(
    result: "GradingResult",
    garment_type: str,
    target_profile: MeasurementProfile,
) -> None:
    """Print grading summary: deltas, convergence, dimensions."""
    from agentic_pattern_engine.models import GradingResult

    print("=" * 60)
    print("GRADING SUMMARY")
    print("=" * 60)

    print(f"\nDeltas (target - source):")
    for field, delta in result.deltas.items():
        print(f"  {field}: {delta:+.2f} cm")

    if result.run_result is not None:
        status = result.run_result.convergence_status.value
        iters = result.run_result.total_iterations
        elapsed = result.run_result.elapsed_time_ms
        print(f"\nSelf-correction: {status}")
        print(f"  Iterations: {iters}")
        print(f"  Time: {elapsed:.1f} ms")

    print(f"\nGraded pieces: {len(result.graded_pieces)}")
    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # --- Grading mode ---
    if args.grade:
        return _run_grade_mode(args)

    profile, garment_type = _load_profile(args)

    # Build thresholds — tight mode uses very low values
    if args.tight_thresholds:
        thresholds = TensionThresholds(
            bust=30.0, waist=25.0, shoulder=40.0,
            armhole=35.0, side_seam=30.0,
            center_front=25.0, center_back=25.0,
        )
    else:
        thresholds = TensionThresholds()

    config = AgentConfig(
        iteration_limit=args.iteration_limit,
        stall_threshold=args.stall_threshold,
        max_ease_tolerance=args.max_ease_tolerance,
        tension_thresholds=thresholds,
    )

    # Select garment spec
    garment_spec = None
    if garment_type == "skirt":
        from agentic_pattern_engine.skirt_generator import (
            SkirtGarmentSpec,
        )
        garment_spec = SkirtGarmentSpec()

    print(f"Running Agentic Pattern Engine...")
    print(f"  Garment: {garment_type}")
    if garment_type == "skirt":
        print(f"  Waist: {profile.waist} cm")
        print(f"  Hip: {profile.hip} cm")
        print(f"  Hip depth: {profile.hip_depth} cm")
        print(f"  Desired length: {profile.desired_length} cm")
    else:
        print(f"  Chest: {profile.chest} cm")
        print(f"  Waist: {profile.waist} cm")
        print(f"  Hip: {profile.hip} cm")
        print(f"  Shoulder: {profile.shoulder_width} cm")
        print(f"  Torso: {profile.torso_length} cm")
    print(f"  Iteration limit: {config.iteration_limit}")
    if args.tight_thresholds:
        print(
            f"  Thresholds: TIGHT "
            f"(bust={thresholds.bust}, waist={thresholds.waist}, ...)"
        )
    print()

    agent = AgentOrchestrator(garment_spec=garment_spec)
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

    # Export 3D body model + pattern pieces as OBJ
    try:
        builder = ParametricBodyModelBuilder()
        body_model = builder.build(profile)
        obj_path = out / "body_model.obj"
        obj_path.write_text(builder.export_obj(body_model))
        print(f"3D Body (OBJ): {obj_path}")
    except Exception as e:
        print(f"Body OBJ export skipped: {e}")

    if result.final_sloper:
        try:
            pattern_obj = ParametricBodyModelBuilder.export_pattern_obj(result.final_sloper)
            pattern_path = out / "pattern.obj"
            pattern_path.write_text(pattern_obj)
            print(f"Pattern (OBJ): {pattern_path}")
        except Exception as e:
            print(f"Pattern OBJ export skipped: {e}")

    # Dump per-iteration pattern OBJs
    if args.dump_iterations and result.audit_trail.entries:
        iter_dir = out / "iterations"
        iter_dir.mkdir(parents=True, exist_ok=True)
        for entry in result.audit_trail.entries:
            try:
                obj_text = ParametricBodyModelBuilder.export_pattern_obj(entry.sloper)
                fname = f"iteration_{entry.iteration:02d}.obj"
                (iter_dir / fname).write_text(obj_text)
            except Exception:
                pass
        print(f"Iteration snapshots: {iter_dir}/ ({len(result.audit_trail.entries)} files)")

    # Generate interactive 3D visualization
    if result.audit_trail.entries:
        try:
            builder = ParametricBodyModelBuilder()
            bm = builder.build(profile)
            html = generate_visualization(bm, result.audit_trail, config.tension_thresholds)
            viz_path = out / "visualization.html"
            viz_path.write_text(html)
            print(f"3D Visualization: {viz_path}")
        except Exception as e:
            print(f"Visualization skipped: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
