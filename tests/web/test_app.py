"""Unit tests for the web app API endpoints."""

from __future__ import annotations

import json
import pathlib

import pytest
from fastapi.testclient import TestClient

from web.app import app

_client = TestClient(app)

_FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text())


def test_web_index_returns_html() -> None:
    r = _client.get("/")
    assert r.status_code == 200
    assert "MANI" in r.text


def test_web_generate_bodice() -> None:
    r = _client.post("/api/generate", json={
        "garment_type": "bodice",
        "chest": 91.5, "waist": 73.5, "hip": 98.0,
        "shoulder_width": 40.0, "torso_length": 42.5,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "converged"
    assert data["garment_type"] == "bodice"
    assert data["iterations"] > 0
    assert data["run_id"]


def test_web_generate_skirt() -> None:
    r = _client.post("/api/generate", json={
        "garment_type": "skirt",
        "waist": 73.5, "hip": 98.0,
        "hip_depth": 20.0, "desired_length": 70.0,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "converged"
    assert data["garment_type"] == "skirt"


def test_web_generate_bodice_missing_fields() -> None:
    r = _client.post("/api/generate", json={
        "garment_type": "bodice",
        "waist": 73.5, "hip": 98.0,
    })
    assert r.status_code == 400


def test_web_generate_skirt_missing_fields() -> None:
    r = _client.post("/api/generate", json={
        "garment_type": "skirt",
        "waist": 73.5, "hip": 98.0,
    })
    assert r.status_code == 400


def test_web_visualization_bodice() -> None:
    r = _client.post("/api/generate", json={
        "garment_type": "bodice",
        "chest": 91.5, "waist": 73.5, "hip": 98.0,
        "shoulder_width": 40.0, "torso_length": 42.5,
    })
    run_id = r.json()["run_id"]
    viz = _client.get(f"/api/visualization/{run_id}")
    assert viz.status_code == 200
    assert "three.js" in viz.text.lower() or "THREE" in viz.text


def test_web_visualization_skirt() -> None:
    r = _client.post("/api/generate", json={
        "garment_type": "skirt",
        "waist": 73.5, "hip": 98.0,
        "hip_depth": 20.0, "desired_length": 70.0,
    })
    run_id = r.json()["run_id"]
    viz = _client.get(f"/api/visualization/{run_id}")
    assert viz.status_code == 200
    assert "Skirt" in viz.text


def test_web_visualization_not_found() -> None:
    r = _client.get("/api/visualization/nonexistent")
    assert r.status_code == 404


def test_web_download_dxf() -> None:
    r = _client.post("/api/generate", json={
        "garment_type": "bodice",
        "chest": 91.5, "waist": 73.5, "hip": 98.0,
        "shoulder_width": 40.0, "torso_length": 42.5,
    })
    run_id = r.json()["run_id"]
    dxf = _client.get(f"/api/download/{run_id}/dxf")
    assert dxf.status_code == 200
    assert len(dxf.content) > 0


def test_web_download_pdf() -> None:
    r = _client.post("/api/generate", json={
        "garment_type": "bodice",
        "chest": 91.5, "waist": 73.5, "hip": 98.0,
        "shoulder_width": 40.0, "torso_length": 42.5,
    })
    run_id = r.json()["run_id"]
    pdf = _client.get(f"/api/download/{run_id}/pdf")
    assert pdf.status_code == 200
    assert len(pdf.content) > 0


def test_web_download_not_found() -> None:
    r = _client.get("/api/download/nonexistent/dxf")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# /api/scan/upload
# ---------------------------------------------------------------------------


def test_web_scan_upload_3dlook_full_body() -> None:
    data = _load_fixture("3dlook_full_body.json")
    r = _client.post("/api/scan/upload", json={"scan_data": data})
    assert r.status_code == 200
    body = r.json()
    assert body["scanner_type"] == "3dlook"
    assert "waist" in body["measurements"]
    assert "chest" in body["measurements"]
    assert body["source_unit"] == "cm"


def test_web_scan_upload_output_unit_inches() -> None:
    data = _load_fixture("3dlook_full_body.json")
    r_cm = _client.post("/api/scan/upload", json={
        "scan_data": data, "output_unit": "cm",
    })
    r_in = _client.post("/api/scan/upload", json={
        "scan_data": data, "output_unit": "in",
    })
    assert r_cm.status_code == 200
    assert r_in.status_code == 200
    cm_vals = r_cm.json()["measurements"]
    in_vals = r_in.json()["measurements"]
    for key in cm_vals:
        expected_in = cm_vals[key] / 2.54
        assert abs(in_vals[key] - expected_in) < 0.01


def test_web_scan_upload_invalid_data_returns_400() -> None:
    r = _client.post("/api/scan/upload", json={
        "scan_data": {"unknown_field": 999},
    })
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# /api/scan/generate
# ---------------------------------------------------------------------------


def test_web_scan_generate_3dlook_full_body() -> None:
    data = _load_fixture("3dlook_full_body.json")
    r = _client.post("/api/scan/generate", json={"scan_data": data})
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"]
    assert body["status"] == "converged"
    assert body["scanner_type"] == "3dlook"
    assert body["iterations"] > 0


def test_web_scan_generate_auto_selects_bodice() -> None:
    data = _load_fixture("3dlook_full_body.json")
    r = _client.post("/api/scan/generate", json={"scan_data": data})
    assert r.status_code == 200
    assert r.json()["garment_type"] == "bodice"


def test_web_scan_generate_with_garment_skirt() -> None:
    data = _load_fixture("3dlook_full_body.json")
    r = _client.post("/api/scan/generate", json={
        "scan_data": data, "garment_type": "skirt",
    })
    assert r.status_code == 200
    assert r.json()["garment_type"] == "skirt"


def test_web_scan_generate_invalid_data_returns_400() -> None:
    r = _client.post("/api/scan/generate", json={
        "scan_data": {"unknown_field": 999},
    })
    assert r.status_code == 400


def test_web_scan_generate_bodice_produces_visualization() -> None:
    data = _load_fixture("3dlook_full_body.json")
    r = _client.post("/api/scan/generate", json={
        "scan_data": data, "garment_type": "bodice",
    })
    assert r.status_code == 200
    run_id = r.json()["run_id"]
    viz = _client.get(f"/api/visualization/{run_id}")
    assert viz.status_code == 200
    assert "Visualization not available" not in viz.text
    assert len(viz.text) > 100


def test_web_scan_generate_skirt_produces_visualization() -> None:
    data = _load_fixture("3dlook_full_body.json")
    r = _client.post("/api/scan/generate", json={
        "scan_data": data, "garment_type": "skirt",
    })
    assert r.status_code == 200
    run_id = r.json()["run_id"]
    viz = _client.get(f"/api/visualization/{run_id}")
    assert viz.status_code == 200
    assert "Visualization not available" not in viz.text
    assert len(viz.text) > 100
