"""First-try events and GET /api/stats (package 7). Runs on SQLite always, and on Postgres too when BOLO_TEST_PG_URL
points at a throwaway database (the fixture drops the rows and events tables, so never point it at a real one)."""
import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from server import db
from server.main import app

client = TestClient(app)
PG_URL = os.environ.get("BOLO_TEST_PG_URL", "")
IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture(params=["sqlite", pytest.param("pg", marks=pytest.mark.skipif(not PG_URL, reason="BOLO_TEST_PG_URL not set"))])
def backend(request, monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    if request.param == "pg":
        import psycopg

        with psycopg.connect(PG_URL, autocommit=True) as conn:
            conn.execute("DROP TABLE IF EXISTS rows")
            conn.execute("DROP TABLE IF EXISTS events")
        monkeypatch.setenv("DATABASE_URL", PG_URL)
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    return request.param


@pytest.fixture()
def clock(backend, monkeypatch):
    """Set the server's clock with clock("2026-11-27 23:59:00") in Asia/Kolkata. The database is opened (and seeded)
    a week earlier first, so the five seed rows never fall on a day under test."""
    now = {"t": datetime(2026, 11, 20, 6, 0, tzinfo=timezone.utc)}
    monkeypatch.setattr(db, "now", lambda: now["t"])
    assert len(client.get("/api/rows").json()["rows"]) == 5

    def set_ist(text):
        now["t"] = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST).astimezone(timezone.utc)
    return set_ist


def event(kind="saved", first_try=True, engine="sample", lang="hi-IN", **extra):
    return client.post("/api/events", json={"kind": kind, "first_try": first_try, "engine": engine, "lang": lang,
                                            "station_id": "oven-line", **extra})


def stats(**params):
    r = client.get("/api/stats", params=params)
    assert r.status_code == 200, r.text
    return r.json()


# kind, first_try, engine, lang
KNOWN = [
    ("saved", True, "sample", "hi-IN"),
    ("saved", True, "sample", "hi-IN"),
    ("discarded", False, "sample", "hi-IN"),
    ("saved", False, "sample", "hi-IN"),
    ("saved", True, "browser", "hi-IN"),
    ("discarded", False, "browser", "mr-IN"),
    ("saved", True, "sarvam", "mr-IN"),
    ("saved", True, "typed", "hi-IN"),
]


def tally(attempts, saved, first_try, discarded, share):
    return {"attempts": attempts, "saved": saved, "first_try": first_try, "discarded": discarded, "first_try_share": share}


def test_events_are_stored_and_counted_per_engine_and_language(clock):
    clock("2026-11-28 10:00:00")
    for kind, first, engine, lang in KNOWN:
        assert event(kind, first, engine, lang).status_code == 204
    body = stats(date="2026-11-28")
    assert body["date"] == "2026-11-28" and body["station_id"] == "oven-line"
    # Worked out by hand from KNOWN, not by the code under test.
    assert body["total"] == tally(8, 6, 5, 2, 0.625)
    assert body["by_engine"] == {
        "browser": tally(2, 1, 1, 1, 0.5),
        "sample": tally(4, 3, 2, 1, 0.5),
        "sarvam": tally(1, 1, 1, 0, 1.0),
        "typed": tally(1, 1, 1, 0, 1.0),
    }
    assert body["by_lang"] == {"hi-IN": tally(6, 5, 4, 1, 0.6667), "mr-IN": tally(2, 1, 1, 1, 0.5)}


def test_first_try_share_counts_discards_against_it(clock):
    clock("2026-11-28 10:00:00")
    for _ in range(18):
        event()
    event(first_try=False)
    event("discarded", False)
    assert stats()["total"] == tally(20, 19, 18, 1, 0.9)  # "First try: 18 of 20 (90%)"


def test_no_events_gives_no_share(clock):
    clock("2026-11-28 10:00:00")
    body = stats()
    assert body["total"] == tally(0, 0, 0, 0, None)
    assert body["by_engine"] == {} and body["by_lang"] == {}


def test_day_boundary_in_kolkata(clock):
    clock("2026-11-27 23:59:00")
    event(engine="browser")
    client.post("/api/rows", json={"station_id": "oven-line", "batch_no": 30, "machine": "Oven 1", "temperature_c": 199,
                                   "rejects": 1, "transcript": "", "source": "typed"})
    clock("2026-11-28 00:01:00")
    event(engine="typed")
    client.post("/api/rows", json={"station_id": "oven-line", "batch_no": 31, "machine": "Oven 2", "temperature_c": 180,
                                   "rejects": 2, "transcript": "", "source": "typed"})
    before, after = stats(date="2026-11-27"), stats(date="2026-11-28")
    assert list(before["by_engine"]) == ["browser"] and list(after["by_engine"]) == ["typed"]
    assert before["shift"] == {"batches": 1, "rejects_by_machine": {"Oven 1": 1, "Oven 2": 0},
                               "out_of_limit": [{"batch_no": 30, "machine": "Oven 1", "field": "temperature_c", "value": 199}],
                               "last_log_at": "2026-11-27T18:29:00Z"}
    assert after["shift"] == {"batches": 1, "rejects_by_machine": {"Oven 1": 0, "Oven 2": 2}, "out_of_limit": [],
                              "last_log_at": "2026-11-27T18:31:00Z"}
    assert stats()["date"] == "2026-11-28"  # with no date, "today" is the day in Asia/Kolkata, not in UTC


def test_shift_summary_lists_each_flag(clock):
    clock("2026-11-28 09:00:00")
    for batch, machine, temp, rejects in [(40, "Oven 1", 196, 7), (41, "Oven 2", 180, 0), (42, "Oven 2", 150, 3)]:
        client.post("/api/rows", json={"station_id": "oven-line", "batch_no": batch, "machine": machine,
                                       "temperature_c": temp, "rejects": rejects, "transcript": "", "source": "typed"})
    shift = stats()["shift"]
    assert shift["batches"] == 3
    assert shift["rejects_by_machine"] == {"Oven 1": 7, "Oven 2": 3}
    assert shift["out_of_limit"] == [
        {"batch_no": 40, "machine": "Oven 1", "field": "temperature_c", "value": 196},
        {"batch_no": 40, "machine": "Oven 1", "field": "rejects", "value": 7},
        {"batch_no": 42, "machine": "Oven 2", "field": "temperature_c", "value": 150},
    ]


@pytest.mark.parametrize("change, error", [
    ({"kind": "discarded", "first_try": True}, "invalid_event"),
    ({"station_id": "nowhere"}, "invalid_event"),
    ({"engine": "wizard"}, "invalid_request"),
    ({"lang": "hindi"}, "invalid_request"),
])
def test_bad_events_are_refused(clock, change, error):
    clock("2026-11-28 10:00:00")
    body = {"kind": "saved", "first_try": True, "engine": "sample", "lang": "hi-IN", "station_id": "oven-line", **change}
    r = client.post("/api/events", json=body)
    assert r.status_code == 422 and r.json()["error"] == error
    assert stats()["total"]["attempts"] == 0
