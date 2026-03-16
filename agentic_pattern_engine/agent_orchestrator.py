"""Agent Orchestrator — the core self-correction loop.

Wires all components together: validate input → generate pieces →
build body model → loop (simulate → detect → check convergence →
check limits → check stall → check oscillation → correct → update
pieces → record) → export → return result.

Accepts an optional GarmentSpec to operate on any garment type.
Defaults to BodiceGarmentSpec for backward compatibility.
"""

from __future__ import annotations

import hashlib
import time
import uuid

from agentic_pattern_engine.audit_trail import AuditTrailRecorder
from agentic_pattern_engine.body_model_builder import ParametricBodyModelBuilder
from agentic_pattern_engine.dxf_exporter import DXFPatternExporter
from agentic_pattern_engine.fit_detector import TensionFitDetector
from agentic_pattern_engine.geometry_corrector import DartEaseGeometryCorrector
from agentic_pattern_engine.models import (
    AgentConfig,
    AgentRunResult,
    AuditEntry,
    BodiceSloper,
    ConvergenceStatus,
    ExportMetadata,
    FitIssue,
    FitIssueType,
    FitRegion,
    MeasurementProfile,
    TensionMap,
)
from agentic_pattern_engine.pdf_exporter import PDFPatternExporter
from agentic_pattern_engine.simulation_engine import MassSpringSimulationEngine
from agentic_pattern_engine.sloper_generator import ParsonsSloperGenerator


class AgentOrchestrator:
    """Execute the full agentic self-correction loop."""

    def __init__(
        self,
        garment_spec: "GarmentSpec | None" = None,
        sloper_generator: ParsonsSloperGenerator | None = None,
        body_model_builder: ParametricBodyModelBuilder | None = None,
        simulation_engine: MassSpringSimulationEngine | None = None,
        fit_detector: TensionFitDetector | None = None,
        geometry_corrector: DartEaseGeometryCorrector | None = None,
        dxf_exporter: DXFPatternExporter | None = None,
        pdf_exporter: PDFPatternExporter | None = None,
    ) -> None:
        # Lazy import to avoid circular dependency
        from agentic_pattern_engine.garment_spec import (
            BodiceGarmentSpec,
        )

        self._spec = garment_spec or BodiceGarmentSpec()
        self._sloper_gen = sloper_generator or ParsonsSloperGenerator()
        self._body_builder = (
            body_model_builder or ParametricBodyModelBuilder()
        )
        self._sim_engine = (
            simulation_engine or MassSpringSimulationEngine()
        )
        self._fit_detector = fit_detector or TensionFitDetector()
        self._corrector = (
            geometry_corrector or DartEaseGeometryCorrector()
        )
        self._dxf_exporter = dxf_exporter or DXFPatternExporter()
        self._pdf_exporter = pdf_exporter or PDFPatternExporter()

    def run(
        self,
        profile: MeasurementProfile,
        config: AgentConfig | None = None,
    ) -> AgentRunResult:
        """Execute the full agentic self-correction loop."""
        start_time = time.perf_counter()
        run_id = str(uuid.uuid4())[:8]
        cfg = config or AgentConfig()
        recorder = AuditTrailRecorder()

        # --- Phase 1: Input validation ---
        profile_errors = self._spec.validate_profile(profile)
        if profile_errors:
            return self._fail_result(
                run_id, ConvergenceStatus.GENERATION_FAILED,
                f"Invalid profile: {'; '.join(profile_errors)}",
                recorder, start_time,
            )

        threshold_errors = cfg.tension_thresholds.validate()
        if threshold_errors:
            return self._fail_result(
                run_id, ConvergenceStatus.GENERATION_FAILED,
                f"Invalid thresholds: {'; '.join(threshold_errors)}",
                recorder, start_time,
            )

        # --- Phase 2: Generation ---
        try:
            pieces = self._spec.generate_initial_pieces(profile)
            body_model = self._body_builder.build(profile)
        except Exception as e:
            return self._fail_result(
                run_id, ConvergenceStatus.GENERATION_FAILED,
                str(e), recorder, start_time,
            )

        # Build a BodiceSloper for backward-compat audit/export
        sloper = self._build_compat_sloper(pieces, profile)

        # Record iteration 0
        recorder.record(AuditEntry(
            iteration=0,
            sloper=sloper,
            tension_map=None,
            fit_issues=[],
            corrections_applied=[],
            total_stress_magnitude=0.0,
            pieces=list(pieces),
        ))

        # --- Phase 3: Self-correction loop ---
        best_pieces = list(pieces)
        best_sloper = sloper
        best_stress = float("inf")
        stress_history: list[float] = []
        issue_history: list[list[FitIssue]] = []
        dampening_factor = 1.0
        last_fit_issues: list[FitIssue] = []

        for iteration in range(1, cfg.iteration_limit + 1):
            # Simulate — use spec's stress computation
            try:
                regional_stresses = self._spec.compute_stress(
                    pieces, profile,
                )
                sim_result = self._sim_engine.simulate(
                    sloper, body_model,
                )
                # Override regional stresses with spec's values
                sim_result.tension_map.regional_stresses = (
                    regional_stresses
                )
            except Exception as e:
                return AgentRunResult(
                    run_id=run_id,
                    convergence_status=(
                        ConvergenceStatus.SIMULATION_FAILED
                    ),
                    final_sloper=best_sloper,
                    total_iterations=iteration - 1,
                    audit_trail=recorder.get_trail(),
                    remaining_fit_issues=last_fit_issues,
                    elapsed_time_ms=self._elapsed(start_time),
                    error_details=str(e),
                    failed_at_iteration=iteration,
                    final_pieces=best_pieces,
                    garment_type=self._spec.garment_type,
                )

            # Detect fit issues
            fit_issues = self._fit_detector.detect(
                sim_result.tension_map,
                body_model,
                cfg.tension_thresholds,
            )

            # Compute total stress magnitude
            total_stress = sum(
                i.violation_magnitude for i in fit_issues
            )

            # Record audit entry
            recorder.record(AuditEntry(
                iteration=iteration,
                sloper=sloper,
                tension_map=sim_result.tension_map,
                fit_issues=fit_issues,
                corrections_applied=[],
                total_stress_magnitude=total_stress,
                pieces=list(pieces),
            ))

            # Track best
            if total_stress < best_stress:
                best_stress = total_stress
                best_sloper = sloper
                best_pieces = list(pieces)

            stress_history.append(total_stress)
            issue_history.append(fit_issues)
            last_fit_issues = fit_issues

            # --- Check convergence ---
            if len(fit_issues) == 0:
                return self._success_result(
                    run_id, ConvergenceStatus.CONVERGED,
                    sloper, pieces, iteration, recorder,
                    profile, [], start_time,
                )

            # --- Check stall ---
            if self._is_stalled(
                stress_history, cfg.stall_threshold,
            ):
                return self._success_result(
                    run_id, ConvergenceStatus.STALLED,
                    best_sloper, best_pieces, iteration,
                    recorder, profile, fit_issues, start_time,
                )

            # --- Check oscillation ---
            if self._detect_oscillation(issue_history):
                dampening_factor *= (
                    cfg.oscillation_dampening_factor
                )

            # --- Apply corrections via spec ---
            corrections = self._spec.plan_corrections(
                fit_issues, pieces, profile, dampening_factor,
            )

            # Update the last audit entry with corrections
            trail = recorder.get_trail()
            trail.entries[-1].corrections_applied = corrections

            pieces = self._spec.apply_corrections(
                pieces, corrections,
            )
            sloper = self._build_compat_sloper(pieces, profile)

        # Iteration limit reached
        return self._success_result(
            run_id, ConvergenceStatus.ITERATION_LIMIT_REACHED,
            best_sloper, best_pieces, cfg.iteration_limit,
            recorder, profile, last_fit_issues, start_time,
        )

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _build_compat_sloper(
        self,
        pieces: list,
        profile: MeasurementProfile,
    ) -> BodiceSloper:
        """Build a BodiceSloper from pieces for backward compat.

        For bodice garments this reconstructs a proper sloper.
        For non-bodice garments it creates a minimal wrapper so
        existing export / audit code doesn't break.
        """
        from agentic_pattern_engine.garment_spec import (
            BodiceGarmentSpec,
        )

        if isinstance(self._spec, BodiceGarmentSpec):
            if self._spec._last_sloper is not None:
                return self._spec._last_sloper
            # Fallback: generate fresh
            return self._sloper_gen.generate(profile)

        # Non-bodice: create a minimal BodiceSloper wrapper
        front = pieces[0] if len(pieces) > 0 else None
        back = pieces[1] if len(pieces) > 1 else front
        if front is None:
            return self._sloper_gen.generate(profile)
        return BodiceSloper(
            sloper_id="compat",
            profile=profile,
            front_bodice=front,
            back_bodice=back,
            bust_ease=0.0,
            waist_ease=0.0,
            metadata={"garment_type": self._spec.garment_type},
        )

    @staticmethod
    def _is_stalled(
        stress_history: list[float], threshold: int,
    ) -> bool:
        """Detect stall: no meaningful improvement over N iterations."""
        if len(stress_history) < threshold:
            return False
        recent = stress_history[-threshold:]
        improvement = recent[0] - recent[-1]
        return improvement < 0.5

    @staticmethod
    def _detect_oscillation(
        issue_history: list[list[FitIssue]],
    ) -> bool:
        """Detect oscillation: a region alternating between
        excess and insufficient."""
        if len(issue_history) < 2:
            return False
        prev = issue_history[-2]
        curr = issue_history[-1]

        prev_map: dict[FitRegion, FitIssueType] = {
            i.region: i.issue_type for i in prev
        }
        curr_map: dict[FitRegion, FitIssueType] = {
            i.region: i.issue_type for i in curr
        }

        for region in prev_map:
            if region in curr_map:
                p, c = prev_map[region], curr_map[region]
                if (
                    (
                        p == FitIssueType.EXCESS_TENSION
                        and c == FitIssueType.INSUFFICIENT_TENSION
                    )
                    or (
                        p == FitIssueType.INSUFFICIENT_TENSION
                        and c == FitIssueType.EXCESS_TENSION
                    )
                ):
                    return True
        return False

    def _success_result(
        self,
        run_id: str,
        status: ConvergenceStatus,
        sloper: BodiceSloper,
        pieces: list,
        total_iterations: int,
        recorder: AuditTrailRecorder,
        profile: MeasurementProfile,
        remaining_issues: list[FitIssue],
        start_time: float,
    ) -> AgentRunResult:
        """Build a successful AgentRunResult with exports."""
        metadata = ExportMetadata(
            profile_hash=hashlib.md5(
                f"{profile.chest}{profile.waist}{profile.hip}"
                .encode()
            ).hexdigest()[:8],
            run_id=run_id,
            iteration_count=total_iterations,
            convergence_status=status.value,
        )

        dxf_bytes = None
        pdf_bytes = None
        try:
            dxf_bytes = self._dxf_exporter.export(
                sloper, metadata,
            )
            pdf_bytes = self._pdf_exporter.export(
                sloper, metadata, profile,
            )
        except Exception:
            pass  # Export errors don't fail the run

        return AgentRunResult(
            run_id=run_id,
            convergence_status=status,
            final_sloper=sloper,
            total_iterations=total_iterations,
            audit_trail=recorder.get_trail(),
            remaining_fit_issues=remaining_issues,
            elapsed_time_ms=self._elapsed(start_time),
            dxf_bytes=dxf_bytes,
            pdf_bytes=pdf_bytes,
            final_pieces=list(pieces),
            garment_type=self._spec.garment_type,
        )

    def _fail_result(
        self,
        run_id: str,
        status: ConvergenceStatus,
        error: str,
        recorder: AuditTrailRecorder,
        start_time: float,
    ) -> AgentRunResult:
        """Build a failed AgentRunResult."""
        return AgentRunResult(
            run_id=run_id,
            convergence_status=status,
            final_sloper=None,
            total_iterations=0,
            audit_trail=recorder.get_trail(),
            remaining_fit_issues=[],
            elapsed_time_ms=self._elapsed(start_time),
            error_details=error,
            garment_type=self._spec.garment_type,
        )

    @staticmethod
    def _elapsed(start_time: float) -> float:
        return (time.perf_counter() - start_time) * 1000.0
