"""Rows storage and endpoints (PRD 6.4). Each test gets its own empty DATA_DIR, so each starts from the five seed rows."""
import re
import sqlite3
import threading
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from server import db, seed
from server.main import app

client = TestClient(app)

GOOD = {"station_id": "oven-line", "batch_no": 14, "machine": "Oven 2", "temperature_c": 180, "rejects": 3,
        "transcript": "Batch chaudah, oven do, ek sau assi degree, teen reject", "source": "sample",
        "audio_url": "/samples/s1.m4a"}


@pytest.fixture(autouse=True)
def fresh_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))


def post(**changes):
    return client.post("/api/rows", json={**GOOD, **changes})


def rows(**params):
    r = client.get("/api/rows", params=params)
    assert r.status_code == 200
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", r.json()["server_time"])
    return r.json()["rows"]


def test_empty_data_dir_seeds_five_rows_once():
    first = rows()
    assert [r["batch_no"] for r in first] == [13, 12, 11, 10, 9]
    assert [r["id"] for r in first] == [5, 4, 3, 2, 1]
    assert {r["source"] for r in first} == {"seed"}
    flags = {r["batch_no"]: (r["temp_out_of_limit"], r["rejects_over_limit"]) for r in first}
    assert flags == {9: (False, False), 10: (False, False), 11: (True, False), 12: (False, True), 13: (False, False)}
    assert rows() == first  # opening the database again does not seed again


@pytest.mark.parametrize("temp, rejects, temp_flag, rejects_flag", [
    (180, 3, False, False), (210, 2, True, False), (181, 7, False, True), (196, 9, True, True),
    (170, 5, False, False), (190, 0, False, False), (169, 6, True, True),
])
def test_post_returns_201_with_server_flags(temp, rejects, temp_flag, rejects_flag):
    r = post(temperature_c=temp, rejects=rejects)
    assert r.status_code == 201
    row = r.json()
    assert (row["temp_out_of_limit"], row["rejects_over_limit"]) == (temp_flag, rejects_flag)
    assert row["id"] == 6
    assert (row["station_name"], row["operator"], row["source"], row["audio_url"]) == \
        ("Oven Line", "Sunita", "sample", "/samples/s1.m4a")
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", row["created_at"])
    assert rows()[0] == row  # what was returned is what was stored


@pytest.mark.parametrize("changes", [
    {"machine": "Oven 3"}, {"temperature_c": 900}, {"batch_no": 0}, {"station_id": "paint-line"},
    {"batch_no": 10000}, {"rejects": 1001}, {"temperature_c": -1}, {"rejects": -1},
])
def test_bad_value_returns_422_and_saves_nothing(changes):
    r = post(**changes)
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_row" and r.json()["message"]
    assert len(rows()) == 5


def test_client_flags_are_ignored():
    r = post(temperature_c=210, rejects=2, temp_out_of_limit=False, rejects_over_limit=True)
    assert r.status_code == 201
    assert (r.json()["temp_out_of_limit"], r.json()["rejects_over_limit"]) == (True, False)
    assert rows()[0]["temp_out_of_limit"] is True


def test_after_id_returns_only_newer_rows_newest_first():
    a = post(batch_no=14).json()["id"]
    b = post(batch_no=15).json()["id"]
    assert (a, b) == (6, 7)
    assert [r["id"] for r in rows(after_id=5)] == [7, 6]
    assert [r["id"] for r in rows(after_id=6)] == [7]
    assert rows(after_id=7) == []
    assert [r["id"] for r in rows()] == [7, 6, 5, 4, 3, 2, 1]
    assert [r["id"] for r in rows(limit=2)] == [7, 6]


@pytest.mark.parametrize("table_exists", [False, True])  # True: the rows were cleared by hand, the table stayed
def test_two_first_requests_seed_once(monkeypatch, tmp_path, table_exists):
    """Hold the first request inside seeding until the second arrives; the write lock must make the second wait."""
    if table_exists:
        with closing(sqlite3.connect(tmp_path / "bolo.db")) as conn:
            conn.execute(db.SCHEMA)
    barrier = threading.Barrier(2, timeout=1)
    real = seed.seed_rows

    def held(start):
        try:
            barrier.wait()  # with the lock the other request never gets here, so this times out after 1 s
        except threading.BrokenBarrierError:
            pass
        return real(start)

    monkeypatch.setattr(seed, "seed_rows", held)
    errors = []

    def first_request():
        try:
            db.list_rows(0, 200)
        except Exception as e:  # a thread's exception is otherwise lost
            errors.append(e)

    threads = [threading.Thread(target=first_request) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(db.list_rows(0, 200)) == 5
