"""The Postgres storage path (used by the hosted demo). Runs only when BOLO_TEST_PG_URL points at a throwaway database:

    docker run -d --rm --name bolo-pg -e POSTGRES_PASSWORD=pw -p 55432:5432 postgres:17-alpine
    BOLO_TEST_PG_URL=postgresql://postgres:pw@localhost:55432/postgres .venv/bin/python -m pytest -q tests/test_rows_pg.py

The test drops the rows table, so never point it at a real database.
"""
import os
import threading

import pytest
from fastapi.testclient import TestClient

PG_URL = os.environ.get("BOLO_TEST_PG_URL", "")
pytestmark = pytest.mark.skipif(not PG_URL, reason="BOLO_TEST_PG_URL not set")


@pytest.fixture()
def client(monkeypatch):
    import psycopg

    with psycopg.connect(PG_URL, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS rows")
    monkeypatch.setenv("DATABASE_URL", PG_URL)
    from server.main import app

    return TestClient(app)


def test_seeds_once_even_with_concurrent_first_requests(client):
    results = []
    threads = [threading.Thread(target=lambda: results.append(client.get("/api/rows").json()["rows"])) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert [len(r) for r in results] == [5] * 6
    rows = client.get("/api/rows").json()["rows"]
    assert [r["batch_no"] for r in rows] == [13, 12, 11, 10, 9]
    assert [(r["temp_out_of_limit"], r["rejects_over_limit"]) for r in rows if r["batch_no"] in (11, 12)] == [(False, True), (True, False)]


def test_post_computes_flags_and_after_id_returns_only_newer(client):
    first = client.get("/api/rows").json()["rows"][0]["id"]
    body = {"station_id": "oven-line", "batch_no": 15, "machine": "Oven 1", "temperature_c": 210, "rejects": 2,
            "transcript": "Batch pandrah", "source": "sample", "audio_url": "/samples/s2.m4a", "temp_out_of_limit": False}
    r = client.post("/api/rows", json=body)
    assert r.status_code == 201
    row = r.json()
    assert row["temp_out_of_limit"] is True and row["rejects_over_limit"] is False
    assert row["id"] > first and row["audio_url"] == "/samples/s2.m4a"
    newer = client.get(f"/api/rows?after_id={first}").json()["rows"]
    assert [x["batch_no"] for x in newer] == [15]


def test_invalid_row_still_refused(client):
    r = client.post("/api/rows", json={"station_id": "oven-line", "batch_no": 1, "machine": "Oven 3", "temperature_c": 180,
                                       "rejects": 0, "transcript": "", "source": "typed"})
    assert r.status_code == 422 and r.json()["error"] == "invalid_row"
