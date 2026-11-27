"""Audit export (package 7): GET /api/rows.csv and GET /api/rows.json, compared cell by cell against known rows.
Runs on SQLite always, and on Postgres too when BOLO_TEST_PG_URL points at a throwaway database."""
import csv
import io
import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from server import db
from server.main import app

client = TestClient(app)
PG_URL = os.environ.get("BOLO_TEST_PG_URL", "")
IST = timezone(timedelta(hours=5, minutes=30))
HEADER = ["id", "created_at", "station_id", "station_name", "operator", "batch_no", "machine", "temperature_c",
          "rejects", "temp_out_of_limit", "rejects_over_limit", "transcript", "source", "audio_url"]
DEVANAGARI = "बैच इक्कीस, ओवन एक, एक सौ छियानवे डिग्री, सात रिजेक्ट"


@pytest.fixture(params=["sqlite", pytest.param("pg", marks=pytest.mark.skipif(not PG_URL, reason="BOLO_TEST_PG_URL not set"))])
def clock(request, monkeypatch, tmp_path):
    """Fresh storage, seeded a week before the days under test; clock("2026-11-28 09:00:05") sets the time in IST."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    if request.param == "pg":
        import psycopg

        with psycopg.connect(PG_URL, autocommit=True) as conn:
            conn.execute("DROP TABLE IF EXISTS rows")
            conn.execute("DROP TABLE IF EXISTS events")
        monkeypatch.setenv("DATABASE_URL", PG_URL)
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    now = {"t": datetime(2026, 11, 20, 6, 0, tzinfo=timezone.utc)}
    monkeypatch.setattr(db, "now", lambda: now["t"])
    assert len(client.get("/api/rows").json()["rows"]) == 5

    def set_ist(text):
        now["t"] = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST).astimezone(timezone.utc)
    return set_ist


def post(batch, machine, temp, rejects, transcript, source, audio_url=None):
    r = client.post("/api/rows", json={"station_id": "oven-line", "batch_no": batch, "machine": machine,
                                       "temperature_c": temp, "rejects": rejects, "transcript": transcript,
                                       "source": source, "audio_url": audio_url})
    assert r.status_code == 201, r.text


def read_csv(**params):
    r = client.get("/api/rows.csv", params=params)
    assert r.status_code == 200, r.text
    return r, list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))


def test_csv_matches_known_rows_cell_by_cell(clock):
    clock("2026-11-28 09:00:05")
    post(21, "Oven 1", 196, 7, DEVANAGARI, "mic_sarvam", "/audio/a1.webm")
    clock("2026-11-28 14:45:02")
    post(22, "Oven 2", 180, 0, "batch twenty two, oven two, \"one eighty\" degree, zero reject", "typed")
    clock("2026-11-28 23:59:59")
    post(23, "Oven 1", 170, 6, "=1+1", "typed")
    r, table = read_csv(**{"from": "2026-11-28", "to": "2026-11-28"})

    assert r.content.startswith(b"\xef\xbb\xbf")  # BOM, so Excel reads UTF-8
    assert r.headers["content-type"] == "text/csv; charset=utf-8"
    assert r.headers["content-disposition"] == 'attachment; filename="bolo-line-oven-line-2026-11-28-to-2026-11-28.csv"'
    assert table == [
        HEADER,
        ["6", "2026-11-28T09:00:05+05:30", "oven-line", "Oven Line", "Sunita", "21", "Oven 1", "196", "7", "yes", "yes",
         DEVANAGARI, "mic_sarvam", "/audio/a1.webm"],
        ["7", "2026-11-28T14:45:02+05:30", "oven-line", "Oven Line", "Sunita", "22", "Oven 2", "180", "0", "no", "no",
         "batch twenty two, oven two, \"one eighty\" degree, zero reject", "typed", ""],
        ["8", "2026-11-28T23:59:59+05:30", "oven-line", "Oven Line", "Sunita", "23", "Oven 1", "170", "6", "no", "yes",
         "'=1+1", "typed", ""],  # a cell a spreadsheet would run as a formula is written as text
    ]


def test_day_boundary_in_kolkata(clock):
    clock("2026-11-27 23:59:00")
    post(30, "Oven 1", 180, 1, "late", "typed")
    clock("2026-11-28 00:01:00")
    post(31, "Oven 2", 180, 2, "early", "typed")
    ids = lambda table: [row[5] for row in table[1:]]  # batch_no column
    assert ids(read_csv(**{"from": "2026-11-27", "to": "2026-11-27"})[1]) == ["30"]
    assert ids(read_csv(**{"from": "2026-11-28", "to": "2026-11-28"})[1]) == ["31"]
    assert ids(read_csv(**{"from": "2026-11-27", "to": "2026-11-28"})[1]) == ["30", "31"]
    r, table = read_csv()  # no dates: today in Asia/Kolkata (it is still the 27th in UTC)
    assert ids(table) == ["31"]
    assert r.headers["content-disposition"].endswith('-2026-11-28-to-2026-11-28.csv"')
    assert read_csv(**{"from": "2026-11-27", "to": "2026-11-27"})[1][1][1] == "2026-11-27T23:59:00+05:30"


def test_json_rows_for_the_print_view(clock):
    clock("2026-11-28 09:00:05")
    post(21, "Oven 1", 196, 7, DEVANAGARI, "mic_sarvam", "/audio/a1.webm")
    r = client.get("/api/rows.json", params={"from": "2026-11-28"})
    assert r.status_code == 200
    body = r.json()
    assert (body["from_date"], body["to_date"]) == ("2026-11-28", "2026-11-28")
    [row] = body["rows"]
    assert (row["batch_no"], row["created_at"], row["transcript"]) == (21, "2026-11-28T03:30:05Z", DEVANAGARI)
    assert (row["temp_out_of_limit"], row["rejects_over_limit"]) == (True, True)


def test_empty_day_gives_header_only_and_bad_range_is_refused(clock):
    clock("2026-11-28 10:00:00")
    assert read_csv()[1] == [HEADER]
    r = client.get("/api/rows.csv", params={"from": "2026-11-28", "to": "2026-11-27"})
    assert r.status_code == 422 and r.json()["error"] == "invalid_range"
    assert client.get("/api/rows.csv", params={"from": "28-11-2026"}).status_code == 422


def test_audit_page_is_served():
    r = client.get("/audit")
    assert r.status_code == 200 and "Production record" in r.text
    assert client.get("/audit/audit.js").status_code == 200
