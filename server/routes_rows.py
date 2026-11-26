"""STUB owned by package 2 (storage). Rows live in memory, pre-filled with the five seed rows."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from . import config
from .contracts import Row, RowIn, RowsResponse

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_row(row_id: int, data: RowIn, created: datetime) -> Row:
    st = config.STATION
    lim = st["limits"]
    return Row(
        id=row_id, created_at=_iso(created), station_id=st["id"], station_name=st["name"],
        operator=st["operator"], batch_no=data.batch_no, machine=data.machine,
        temperature_c=data.temperature_c, rejects=data.rejects,
        temp_out_of_limit=not (lim["temperature_c"]["min"] <= data.temperature_c <= lim["temperature_c"]["max"]),
        rejects_over_limit=data.rejects > lim["rejects"]["max"],
        transcript=data.transcript, source=data.source, audio_url=data.audio_url,
    )


_SEED = [(9, "Oven 1", 178, 1), (10, "Oven 2", 182, 0), (11, "Oven 1", 196, 2), (12, "Oven 2", 181, 7), (13, "Oven 1", 176, 3)]
_start = _now() - timedelta(hours=3)
ROWS: list[Row] = [
    _make_row(i + 1, RowIn(station_id="oven-line", batch_no=b, machine=m, temperature_c=t, rejects=r,
                           transcript="", source="seed"), _start + timedelta(minutes=40 * i))
    for i, (b, m, t, r) in enumerate(_SEED)
]


@router.post("/api/rows", response_model=Row, status_code=201)
def add_row(data: RowIn):
    row = _make_row(len(ROWS) + 1, data, _now())
    ROWS.append(row)
    return row


@router.get("/api/rows", response_model=RowsResponse)
def list_rows(after_id: int = 0, limit: int = 200):
    rows = [r for r in ROWS if r.id > after_id][::-1][:limit]
    return RowsResponse(rows=rows, server_time=_iso(_now()))
