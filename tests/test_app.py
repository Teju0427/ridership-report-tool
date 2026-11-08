"""
Automated tests. Run:  pytest
Each test uses a fresh temporary database, so tests never touch your real data.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import database as db
from backend.main import app

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")  # temporary DB
    with TestClient(app) as c:      # 'with' triggers the startup (creates table)
        yield c


def upload(client, name):
    with open(DATA / name, "rb") as f:
        return client.post("/api/upload", files={"file": (name, f, "text/csv")})


def test_upload_sample_saves_all_rows(client):
    r = upload(client, "sample_ridership.csv")
    assert r.status_code == 200
    assert r.json()["rejected_rows"] == 0
    assert r.json()["saved_rows"] > 10000


def test_messy_file_rejects_bad_rows(client):
    r = upload(client, "messy_example.csv").json()
    assert r["saved_rows"] == 2
    assert r["rejected_rows"] == 5


def test_same_file_twice_does_not_double_count(client):
    upload(client, "sample_ridership.csv")
    first = client.get("/api/dashboard").json()["summary"]["total"]
    upload(client, "sample_ridership.csv")
    second = client.get("/api/dashboard").json()["summary"]["total"]
    assert first == second


def test_bad_date_filter_returns_400(client):
    assert client.get("/api/dashboard?start=2026-10-31&end=2026-10-01").status_code == 400
    assert client.get("/api/dashboard?start=yesterday").status_code == 400


def test_excel_report_downloads(client):
    upload(client, "sample_ridership.csv")
    r = client.get("/api/report.xlsx?start=2026-10-01&end=2026-10-31")
    assert r.status_code == 200
    assert r.content[:2] == b"PK"   # .xlsx files are zip files -> start with 'PK'
