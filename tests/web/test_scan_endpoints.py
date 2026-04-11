"""Unit tests for web scan upload and generate endpoints."""
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


# ---------------------------------------------------------------------------
# /api/scan/upload
# ---------------------------------------------------------------------------


def test_scan_upload_3dlook_full_body() -> None:
    data = _load_fixture("3dlook_full_body.json")
    r = _client.post("/api/scan/upload", json={
        "scan_data": data,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["scanner_type"] == "3dlook"
    assert "waist" in body["measurements"]
    assert "chest" in body["measurements"]
    assert "hip" in body["measurements"]
    assert body["source_unit"] == "cm"


def test_scan_upload_output_unit_inches() -> None:
    data = _load_fixture("3dlook_full_body.json")
    r_cm = _client.post("/api/scan/upload", json={
        "scan_data": data,
        "output_unit": "cm",
    })
    r_in = _client.post("/api/scan/upload", json={
        "scan_data": data,
        "output_unit": "in",
    })
    assert r_cm.status_code == 200
    assert r_in.status_code == 200
    cm_vals = r_cm.json()["measurements"]
    in_vals = r_in.json()["measurements"]
    for key in cm_vals:
        expected_in = cm_vals[key] / 2.54
        assert abs(in_vals[key] - expected_in) < 0.01


def test_scan_upload_invalid_data_returns_400() -> None:
    r = _client.post("/api/scan/upload", json={
        "scan_data": {"unknown_field": 999},
    })
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# /api/scan/generate
# ---------------------------------------------------------------------------


def test_scan_generate_3dlook_full_body() -> None:
    data = _load_fixture("3dlook_full_body.json")
    r = _client.post("/api/scan/generate", json={
        "scan_data": data,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"]
    assert body["status"] == "converged"
    assert body["scanner_type"] == "3dlook"
    assert body["iterations"] > 0


def test_scan_generate_auto_selects_bodice() -> None:
    data = _load_fixture("3dlook_full_body.json")
    r = _client.post("/api/scan/generate", json={
        "scan_data": data,
    })
    assert r.status_code == 200
    assert r.json()["garment_type"] == "bodice"


def test_scan_generate_with_garment_skirt() -> None:
    data = _load_fixture("3dlook_full_body.json")
    r = _client.post("/api/scan/generate", json={
        "scan_data": data,
        "garment_type": "skirt",
    })
    assert r.status_code == 200
    assert r.json()["garment_type"] == "skirt"


def test_scan_generate_invalid_data_returns_400() -> None:
    r = _client.post("/api/scan/generate", json={
        "scan_data": {"unknown_field": 999},
    })
    assert r.status_code == 400
