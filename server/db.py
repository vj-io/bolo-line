"""SQLite storage for rows (PRD 3.3). A short-lived connection per call; the table is created and seeded lazily."""
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

from . import config, seed

SCHEMA = """CREATE TABLE IF NOT EXISTS rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    station_id TEXT NOT NULL,
    station_name TEXT NOT NULL,
    operator TEXT NOT NULL,
    batch_no INTEGER NOT NULL,
    machine TEXT NOT NULL,
    temperature_c INTEGER NOT NULL,
    rejects INTEGER NOT NULL,
    temp_out_of_limit INTEGER NOT NULL,
    rejects_over_limit INTEGER NOT NULL,
    transcript TEXT NOT NULL,
    source TEXT NOT NULL,
    audio_url TEXT
)"""
COLUMNS = ("created_at", "station_id", "station_name", "operator", "batch_no", "machine", "temperature_c",
           "rejects", "temp_out_of_limit", "rejects_over_limit", "transcript", "source", "audio_url")


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def flags(station: dict, temperature_c: int, rejects: int) -> dict:
    """Always computed here from the station limits; a client never sets them."""
    lim = station["limits"]
    return {"temp_out_of_limit": not lim["temperature_c"]["min"] <= temperature_c <= lim["temperature_c"]["max"],
            "rejects_over_limit": rejects > lim["rejects"]["max"]}


def _insert(conn: sqlite3.Connection, station: dict, fields: dict, created_at: datetime) -> int:
    row = {"created_at": iso(created_at), "station_id": station["id"], "station_name": station["name"],
           "operator": station["operator"], **fields, **flags(station, fields["temperature_c"], fields["rejects"])}
    cur = conn.execute(f"INSERT INTO rows ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
                       [row[c] for c in COLUMNS])
    return cur.lastrowid


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.data_dir() / "bolo.db", isolation_level=None)  # autocommit outside BEGIN
    conn.row_factory = sqlite3.Row
    # Take the write lock before the empty check, so two first requests cannot both seed.
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM rows").fetchone()[0] == 0:
        for created_at, fields in seed.seed_rows(now() - timedelta(hours=3)):
            _insert(conn, config.STATION, fields, created_at)
    conn.execute("COMMIT")
    return conn


def add_row(station: dict, fields: dict) -> dict:
    """Insert a validated row; returns it as stored."""
    with closing(_connect()) as conn:
        row_id = _insert(conn, station, fields, now())
        return dict(conn.execute("SELECT * FROM rows WHERE id = ?", (row_id,)).fetchone())


def list_rows(after_id: int, limit: int) -> list[dict]:
    """Rows with id > after_id, newest first."""
    with closing(_connect()) as conn:
        cur = conn.execute("SELECT * FROM rows WHERE id > ? ORDER BY id DESC LIMIT ?", (after_id, limit))
        return [dict(r) for r in cur]
