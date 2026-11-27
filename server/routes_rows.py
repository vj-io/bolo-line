"""POST and GET /api/rows (PRD 3.4), stored in SQLite through server/db.py."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from . import config, db
from .contracts import ErrorBody, Row, RowIn, RowsResponse

router = APIRouter()

RANGES = {"batch_no": (1, 9999), "temperature_c": (0, 400), "rejects": (0, 1000)}


def _invalid(message: str) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": "invalid_row", "message": message})


@router.post("/api/rows", response_model=Row, status_code=201, responses={422: {"model": ErrorBody}})
def add_row(data: RowIn):
    station = config.get_station(data.station_id)
    if station is None:
        return _invalid(f"unknown station: {data.station_id}")
    machines = [m["name"] for m in station["machines"]]
    if data.machine not in machines:
        return _invalid(f"unknown machine: {data.machine} (expected {' or '.join(machines)})")
    for field, (low, high) in RANGES.items():
        value = getattr(data, field)
        if not low <= value <= high:
            return _invalid(f"{field} {value} is outside {low} to {high}")
    return db.add_row(station, data.model_dump(exclude={"station_id"}))


@router.get("/api/rows", response_model=RowsResponse)
def list_rows(after_id: int = 0, limit: int = 200):
    return {"rows": db.list_rows(after_id, limit), "server_time": db.iso(db.now())}
