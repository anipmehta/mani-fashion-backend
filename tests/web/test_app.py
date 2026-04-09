"""Unit tests for the web app API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from web.app import app

_client = TestClient(app)


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
