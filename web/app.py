"""MANI Web App — FastAPI backend for pattern generation.

Endpoints:
  GET  /                          → HTML form
  POST /api/generate              → run engine, return result
  POST /api/grade                 → grade existing DXF to new measurements
  GET  /api/visualization/{id}    → Three.js HTML for a run
  GET  /api/download/{id}/dxf     → DXF pattern file
  GET  /api/download/{id}/pdf     → PDF pattern file
  POST /api/scan/upload           → parse scan data, return measurements
  POST /api/scan/generate         → parse scan, run engine, return result
"""

from __future__ import annotations

import base64
import tempfile
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agentic_pattern_engine.agent_orchestrator import AgentOrchestrator
from agentic_pattern_engine.garment_spec import BodiceGarmentSpec
from agentic_pattern_engine.grading_engine import GradingEngine
from agentic_pattern_engine.models import (
    AgentConfig,
    MeasurementProfile,
    SkirtMeasurementProfile,
)
from agentic_pattern_engine.pattern_parser import PatternParser
from agentic_pattern_engine.scanner import (
    AdapterRegistry,
    GarmentHint,
    scan_result_to_bodice_profile,
    scan_result_to_skirt_profile,
)
from agentic_pattern_engine.skirt_generator import SkirtGarmentSpec
from agentic_pattern_engine.units import cm_to_inches

app = FastAPI(title="MANI Pattern Engine")

# ── Garment type constants ──────────────────────────────────────────────
GARMENT_BODICE: str = "bodice"
GARMENT_SKIRT: str = "skirt"

# Serve static files (HTML frontend)
import pathlib
_STATIC_DIR = pathlib.Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Serve the main HTML page."""
    return (_STATIC_DIR / "index.html").read_text()

# In-memory store for run results (demo only)
_runs: dict[str, Any] = {}


class GenerateRequest(BaseModel):
    garment_type: str = GARMENT_BODICE
    chest: float | None = None
    waist: float
    hip: float
    shoulder_width: float | None = None
    torso_length: float | None = None
    hip_depth: float | None = None
    desired_length: float | None = None


class GenerateResponse(BaseModel):
    run_id: str
    status: str
    iterations: int
    garment_type: str
    elapsed_ms: float
    errors: list[str] | None = None


@app.post("/api/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    """Run the pattern engine and store results."""
    errors: list[str] = []

    if req.garment_type == GARMENT_SKIRT:
        if not req.hip_depth or not req.desired_length:
            raise HTTPException(
                400,
                "hip_depth and desired_length required for skirt",
            )
        profile = SkirtMeasurementProfile(
            waist=req.waist,
            hip=req.hip,
            hip_depth=req.hip_depth,
            desired_length=req.desired_length,
        )
        spec = SkirtGarmentSpec()
    else:
        if not req.chest or not req.shoulder_width or not req.torso_length:
            raise HTTPException(
                400,
                "chest, shoulder_width, torso_length required for bodice",
            )
        profile = MeasurementProfile(
            chest=req.chest,
            waist=req.waist,
            hip=req.hip,
            shoulder_width=req.shoulder_width,
            torso_length=req.torso_length,
        )
        spec = BodiceGarmentSpec()

    orch = AgentOrchestrator(garment_spec=spec)
    result = orch.run(profile, AgentConfig(iteration_limit=20))

    run_id = str(uuid.uuid4())[:8]

    # Generate visualization HTML
    viz_html = None
    if req.garment_type == GARMENT_BODICE:
        try:
            from agentic_pattern_engine.body_model_builder import (
                ParametricBodyModelBuilder,
            )
            from agentic_pattern_engine.html_visualizer import (
                generate_visualization,
            )

            bm = ParametricBodyModelBuilder().build(profile)
            viz_html = generate_visualization(
                bm, result.audit_trail,
            )
        except Exception:
            pass
    elif req.garment_type == GARMENT_SKIRT:
        try:
            from agentic_pattern_engine.skirt_visualizer import (
                generate_skirt_visualization,
            )

            viz_html = generate_skirt_visualization(
                profile, result.audit_trail,
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Skirt viz error: {e}")

    _runs[run_id] = {
        "result": result,
        "profile": profile,
        "garment_type": req.garment_type,
        "viz_html": viz_html,
    }

    return GenerateResponse(
        run_id=run_id,
        status=result.convergence_status.value,
        iterations=result.total_iterations,
        garment_type=req.garment_type,
        elapsed_ms=round(result.elapsed_time_ms, 1),
        errors=[result.error_details] if result.error_details else None,
    )


# ---------------------------------------------------------------------------
# Grade endpoint models
# ---------------------------------------------------------------------------


class GradeRequest(BaseModel):
    dxf_content_base64: str
    garment_type: str = GARMENT_BODICE
    chest: float | None = None
    waist: float | None = None
    hip: float | None = None
    shoulder_width: float | None = None
    torso_length: float | None = None
    hip_depth: float | None = None
    desired_length: float | None = None


class GradeResponse(BaseModel):
    run_id: str
    status: str
    iterations: int
    garment_type: str
    elapsed_ms: float
    deltas: dict[str, float]
    warnings: list[str]
    pieces_count: int
    detected_garment_type: str | None = None


# ---------------------------------------------------------------------------
# Grade endpoint
# ---------------------------------------------------------------------------


def _build_target_profile(
    req: GradeRequest,
) -> MeasurementProfile | SkirtMeasurementProfile:
    """Build a target measurement profile from grade request fields."""
    if req.garment_type == GARMENT_SKIRT:
        if not req.waist or not req.hip or not req.hip_depth or not req.desired_length:
            raise HTTPException(
                400,
                "waist, hip, hip_depth, and desired_length required for skirt grading",
            )
        return SkirtMeasurementProfile(
            waist=req.waist,
            hip=req.hip,
            hip_depth=req.hip_depth,
            desired_length=req.desired_length,
        )
    # Bodice
    if not req.chest or not req.waist or not req.hip:
        raise HTTPException(
            400,
            "chest, waist, and hip required for bodice grading",
        )
    if not req.shoulder_width or not req.torso_length:
        raise HTTPException(
            400,
            "shoulder_width and torso_length required for bodice grading",
        )
    return MeasurementProfile(
        chest=req.chest,
        waist=req.waist,
        hip=req.hip,
        shoulder_width=req.shoulder_width,
        torso_length=req.torso_length,
    )


@app.post("/api/grade", response_model=GradeResponse)
def grade(req: GradeRequest) -> GradeResponse:
    """Grade an existing DXF pattern to new target measurements."""
    # Decode base64 DXF content
    try:
        dxf_bytes = base64.b64decode(req.dxf_content_base64)
    except Exception as exc:
        raise HTTPException(400, detail=f"Invalid base64 content: {exc}")

    # Write to temp file and parse
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".dxf", delete=False,
        ) as tmp:
            tmp.write(dxf_bytes)
            tmp_path = tmp.name

        parser = PatternParser()
        parse_result = parser.parse(tmp_path)
    except Exception as exc:
        raise HTTPException(400, detail=f"Failed to parse DXF: {exc}")

    if parse_result.errors:
        raise HTTPException(
            400,
            detail=f"DXF parse errors: {'; '.join(parse_result.errors)}",
        )

    if not parse_result.pieces:
        raise HTTPException(400, detail="No pattern pieces found in DXF")

    # Auto-detect garment type from parsed pieces and block mismatches
    detected_garment_type = parse_result.garment_type
    if detected_garment_type and detected_garment_type != req.garment_type:
        raise HTTPException(
            400,
            detail=(
                f"Uploaded pattern is a {detected_garment_type} pattern "
                f"but {req.garment_type} grading was requested"
            ),
        )

    # Build target profile
    target_profile = _build_target_profile(req)

    # Select garment spec and build orchestrator
    if req.garment_type == GARMENT_SKIRT:
        spec = SkirtGarmentSpec()
    else:
        spec = BodiceGarmentSpec()

    orch = AgentOrchestrator(garment_spec=spec)

    # Run grading engine with self-correction
    grading_engine = GradingEngine(orchestrator=orch)

    # Build source profile from parsed DXF metadata
    source_profile = MeasurementProfile(
        chest=target_profile.chest if hasattr(target_profile, "chest") else 91.5,
        waist=target_profile.waist if hasattr(target_profile, "waist") else 73.5,
        hip=target_profile.hip if hasattr(target_profile, "hip") else 98.0,
        shoulder_width=(
            target_profile.shoulder_width
            if hasattr(target_profile, "shoulder_width")
            else 40.0
        ),
        torso_length=(
            target_profile.torso_length
            if hasattr(target_profile, "torso_length")
            else 42.5
        ),
    )

    grading_result = grading_engine.grade(
        pieces=parse_result.pieces,
        source_profile=source_profile,
        target_profile=target_profile,
        garment_type=req.garment_type,
    )

    run_id = str(uuid.uuid4())[:8]

    # Determine convergence info from run_result
    if grading_result.run_result is not None:
        status = grading_result.run_result.convergence_status.value
        iterations = grading_result.run_result.total_iterations
        elapsed_ms = round(grading_result.run_result.elapsed_time_ms, 1)
    else:
        status = "graded"
        iterations = 0
        elapsed_ms = 0.0

    # Generate visualization HTML
    viz_html = None
    if req.garment_type == GARMENT_BODICE:
        try:
            from agentic_pattern_engine.body_model_builder import (
                ParametricBodyModelBuilder,
            )
            from agentic_pattern_engine.html_visualizer import (
                generate_visualization,
            )

            if grading_result.run_result and grading_result.run_result.audit_trail:
                bm = ParametricBodyModelBuilder().build(target_profile)
                viz_html = generate_visualization(
                    bm, grading_result.run_result.audit_trail,
                )
        except Exception:
            pass
    elif req.garment_type == GARMENT_SKIRT:
        try:
            from agentic_pattern_engine.skirt_visualizer import (
                generate_skirt_visualization,
            )

            if grading_result.run_result and grading_result.run_result.audit_trail:
                viz_html = generate_skirt_visualization(
                    target_profile, grading_result.run_result.audit_trail,
                )
        except Exception:
            pass

    _runs[run_id] = {
        "result": grading_result.run_result,
        "profile": target_profile,
        "garment_type": req.garment_type,
        "viz_html": viz_html,
    }

    return GradeResponse(
        run_id=run_id,
        status=status,
        iterations=iterations,
        garment_type=req.garment_type,
        elapsed_ms=elapsed_ms,
        deltas=grading_result.deltas,
        warnings=grading_result.warnings,
        pieces_count=len(grading_result.graded_pieces),
        detected_garment_type=detected_garment_type,
    )


@app.get("/api/visualization/{run_id}", response_class=HTMLResponse)
def visualization(run_id: str) -> str:
    """Return the Three.js visualization HTML."""
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run["viz_html"]:
        return run["viz_html"]
    return "<html><body><p>Visualization not available for this garment type.</p></body></html>"


@app.get("/api/download/{run_id}/dxf")
def download_dxf(run_id: str) -> Response:
    """Download DXF pattern file."""
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    result = run["result"]
    if not result.dxf_bytes:
        raise HTTPException(404, "DXF not available")
    return Response(
        content=result.dxf_bytes,
        media_type="application/dxf",
        headers={"Content-Disposition": f"attachment; filename=pattern_{run_id}.dxf"},
    )


@app.get("/api/download/{run_id}/pdf")
def download_pdf(run_id: str) -> Response:
    """Download PDF pattern file."""
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    result = run["result"]
    if not result.pdf_bytes:
        raise HTTPException(404, "PDF not available")
    return Response(
        content=result.pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=pattern_{run_id}.pdf"},
    )


# ---------------------------------------------------------------------------
# Scan endpoint models
# ---------------------------------------------------------------------------


class ScanUploadRequest(BaseModel):
    scan_data: dict
    output_unit: str = "cm"


class ScanUploadResponse(BaseModel):
    measurements: dict[str, float]
    scanner_type: str
    garment_hints: str
    confidence_scores: dict[str, float] | None
    source_unit: str


class ScanGenerateRequest(BaseModel):
    scan_data: dict
    garment_type: str | None = None


class ScanGenerateResponse(BaseModel):
    run_id: str
    status: str
    iterations: int
    garment_type: str
    elapsed_ms: float
    scanner_type: str
    measurements: dict[str, float]


# ---------------------------------------------------------------------------
# Scan endpoints
# ---------------------------------------------------------------------------


@app.post("/api/scan/upload", response_model=ScanUploadResponse)
def scan_upload(req: ScanUploadRequest) -> ScanUploadResponse:
    """Parse scan data and return mapped measurements."""
    try:
        scan_result = AdapterRegistry().parse(req.scan_data)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    measurements = dict(scan_result.measurements)
    if req.output_unit == "in":
        measurements = {
            k: cm_to_inches(v) for k, v in measurements.items()
        }

    return ScanUploadResponse(
        measurements=measurements,
        scanner_type=scan_result.scanner_type,
        garment_hints=scan_result.garment_hints.value,
        confidence_scores=scan_result.confidence_scores,
        source_unit=scan_result.source_unit,
    )


@app.post("/api/scan/generate", response_model=ScanGenerateResponse)
def scan_generate(req: ScanGenerateRequest) -> ScanGenerateResponse:
    """Parse scan data, build profile, run engine, return results."""
    try:
        scan_result = AdapterRegistry().parse(req.scan_data)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    # Determine garment type
    if req.garment_type is not None:
        garment_type = req.garment_type
    else:
        hint = scan_result.garment_hints
        if hint in (GarmentHint.BOTH, GarmentHint.BODICE_ONLY):
            garment_type = GARMENT_BODICE
        elif hint == GarmentHint.SKIRT_ONLY:
            garment_type = GARMENT_SKIRT
        else:
            raise HTTPException(
                400,
                detail="Insufficient measurements for any garment type",
            )

    # Convert to profile and select spec
    try:
        if garment_type == GARMENT_SKIRT:
            profile = scan_result_to_skirt_profile(scan_result)
            spec = SkirtGarmentSpec()
        else:
            profile = scan_result_to_bodice_profile(scan_result)
            spec = BodiceGarmentSpec()
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    orch = AgentOrchestrator(garment_spec=spec)
    result = orch.run(profile, AgentConfig(iteration_limit=20))

    run_id = str(uuid.uuid4())[:8]

    # Generate visualization HTML (same logic as /api/generate)
    viz_html = None
    if garment_type == GARMENT_BODICE:
        try:
            from agentic_pattern_engine.body_model_builder import (
                ParametricBodyModelBuilder,
            )
            from agentic_pattern_engine.html_visualizer import (
                generate_visualization,
            )

            bm = ParametricBodyModelBuilder().build(profile)
            viz_html = generate_visualization(
                bm, result.audit_trail,
            )
        except Exception:
            pass
    elif garment_type == GARMENT_SKIRT:
        try:
            from agentic_pattern_engine.skirt_visualizer import (
                generate_skirt_visualization,
            )

            viz_html = generate_skirt_visualization(
                profile, result.audit_trail,
            )
        except Exception:
            pass

    _runs[run_id] = {
        "result": result,
        "profile": profile,
        "garment_type": garment_type,
        "viz_html": viz_html,
    }

    return ScanGenerateResponse(
        run_id=run_id,
        status=result.convergence_status.value,
        iterations=result.total_iterations,
        garment_type=garment_type,
        elapsed_ms=round(result.elapsed_time_ms, 1),
        scanner_type=scan_result.scanner_type,
        measurements=dict(scan_result.measurements),
    )
