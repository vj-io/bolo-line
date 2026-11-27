"""Package 7 storage: one event per finished attempt (saved or discarded), next to the rows table, plus the day-range
reads that the stats and export routes share. SQLite by default, Postgres when DATABASE_URL is set, through the
connection helpers in server/db.py. A "day" is a calendar day in Asia/Kolkata."""
from contextlib import closing
from datetime import date, datetime, timedelta, timezone

from . import config, db

# ponytail: India has kept UTC+05:30 with no daylight saving since 1945, so a fixed offset is exact and needs no tzdata
# in the slim container. Use zoneinfo if a station ever sits in a zone with daylight saving.
IST = timezone(timedelta(hours=5, minutes=30), "IST")

SCHEMA = """CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    station_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    first_try INTEGER NOT NULL,
    engine TEXT NOT NULL,
    lang TEXT NOT NULL
)"""
PG_SCHEMA = """CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    created_at TEXT NOT NULL,
    station_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    first_try BOOLEAN NOT NULL,
    engine TEXT NOT NULL,
    lang TEXT NOT NULL
)"""


def _query(sql: str, params: tuple = ()) -> list[dict]:
    """Run one statement (written with ? placeholders) after making sure the events table exists; returns its rows."""
    if db._pg_url():
        def work(conn):
            conn.execute(PG_SCHEMA)
            cur = conn.execute(sql.replace("?", "%s"), params)
            return [dict(r) for r in cur.fetchall()] if cur.description else []
        return db._pg(work)
    with closing(db._connect()) as conn:
        conn.execute(SCHEMA)
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def today() -> date:
    return db.now().astimezone(IST).date()


def day_bounds(first: date, last: date) -> tuple[str, str]:
    """UTC ISO strings [start, end) covering the Asia/Kolkata days first to last. Stored times share one fixed
    format (YYYY-MM-DDTHH:MM:SSZ), so they compare correctly as strings."""
    start = datetime.combine(first, datetime.min.time(), IST)
    end = datetime.combine(last + timedelta(days=1), datetime.min.time(), IST)
    return db.iso(start.astimezone(timezone.utc)), db.iso(end.astimezone(timezone.utc))


def to_ist(created_at: str) -> str:
    """2026-11-28T09:15:02Z -> 2026-11-28T14:45:02+05:30"""
    return datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(IST).isoformat()


def add_event(station_id: str, kind: str, first_try: bool, engine: str, lang: str) -> None:
    _query("INSERT INTO events (created_at, station_id, kind, first_try, engine, lang) VALUES (?, ?, ?, ?, ?, ?)",
           (db.iso(db.now()), station_id, kind, first_try, engine, lang))


def events_on(station_id: str, day: date) -> list[dict]:
    start, end = day_bounds(day, day)
    return _query("SELECT * FROM events WHERE station_id = ? AND created_at >= ? AND created_at < ? ORDER BY id",
                  (station_id, start, end))


def rows_between(station_id: str, first: date, last: date) -> list[dict]:
    """Rows logged on the Asia/Kolkata days first to last, oldest first, with the flags as booleans."""
    start, end = day_bounds(first, last)
    rows = _query("SELECT * FROM rows WHERE station_id = ? AND created_at >= ? AND created_at < ? ORDER BY id",
                  (station_id, start, end))
    for r in rows:
        r["temp_out_of_limit"], r["rejects_over_limit"] = bool(r["temp_out_of_limit"]), bool(r["rejects_over_limit"])
    return rows


def tally(events: list[dict]) -> dict:
    """Attempts, saved, saved on the first try, discarded, and the first-try share of all attempts. A discarded
    attempt counts against the share: that is what keeps the figure honest."""
    saved = [e for e in events if e["kind"] == "saved"]
    first = sum(1 for e in saved if e["first_try"])
    n = len(events)
    return {"attempts": n, "saved": len(saved), "first_try": first, "discarded": n - len(saved),
            "first_try_share": round(first / n, 4) if n else None}


def tally_by(events: list[dict], key: str) -> dict:
    return {k: tally([e for e in events if e[key] == k]) for k in sorted({e[key] for e in events})}


def shift_summary(rows: list[dict], station: dict) -> dict:
    """The end-of-shift card: batches logged, the out-of-limit list, rejects per machine, the last log time."""
    out = []
    for r in rows:
        if r["temp_out_of_limit"]:
            out.append({"batch_no": r["batch_no"], "machine": r["machine"], "field": "temperature_c", "value": r["temperature_c"]})
        if r["rejects_over_limit"]:
            out.append({"batch_no": r["batch_no"], "machine": r["machine"], "field": "rejects", "value": r["rejects"]})
    rejects = {m["name"]: 0 for m in station["machines"]}
    for r in rows:
        rejects[r["machine"]] = rejects.get(r["machine"], 0) + r["rejects"]
    return {"batches": len(rows), "out_of_limit": out, "rejects_by_machine": rejects,
            "last_log_at": max((r["created_at"] for r in rows), default=None)}


def stats(station_id: str, day: date) -> dict:
    events = events_on(station_id, day)
    return {"date": day.isoformat(), "station_id": station_id, "total": tally(events),
            "by_engine": tally_by(events, "engine"), "by_lang": tally_by(events, "lang"),
            "shift": shift_summary(rows_between(station_id, day, day), config.get_station(station_id))}
