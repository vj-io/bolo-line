"""POST /api/events and GET /api/stats (package 7): the first-try figure and the end-of-shift summary."""
from datetime import date
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from . import config, events
from .contracts import ErrorBody, EventIn, StatsResponse

router = APIRouter()


def _invalid(message: str) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": "invalid_event", "message": message})


@router.post("/api/events", status_code=204, responses={422: {"model": ErrorBody}})
def add_event(data: EventIn):
    if config.get_station(data.station_id) is None:
        return _invalid(f"unknown station: {data.station_id}")
    if data.kind == "discarded" and data.first_try:
        return _invalid("a discarded attempt cannot be a first try")
    events.add_event(data.station_id, data.kind, data.first_try, data.engine, data.lang)


@router.get("/api/stats", response_model=StatsResponse, responses={404: {"model": ErrorBody}})
def stats(date: Optional[date] = None, station_id: str = config.STATION["id"]):
    if config.get_station(station_id) is None:
        return JSONResponse(status_code=404, content={"error": "unknown_station", "message": station_id})
    return events.stats(station_id, date or events.today())
