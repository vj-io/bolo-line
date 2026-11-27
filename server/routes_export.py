"""Audit export (package 7): GET /api/rows.csv for a spreadsheet and GET /api/rows.json for the print view at /audit.
Both cover whole days in Asia/Kolkata, oldest row first. Wording: a production record, never "FSSAI-compliant"."""
import csv
import io
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response

from . import config, events
from .contracts import ErrorBody, RowsRangeResponse

router = APIRouter()

CSV_COLUMNS = ["id", "created_at", "station_id", "station_name", "operator", "batch_no", "machine", "temperature_c",
               "rejects", "temp_out_of_limit", "rejects_over_limit", "transcript", "source", "audio_url"]
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")  # a spreadsheet would run a cell starting with these as a formula


def _range(from_date: Optional[date], to_date: Optional[date]):
    """Neither given: today. Only from: from to today. Only to: that one day."""
    last = to_date or events.today()
    first = from_date or last
    return None if last < first else (first, last)


def _bad_range():
    return JSONResponse(status_code=422, content={"error": "invalid_range", "message": "to is before from"})


def csv_cell(column: str, value) -> str:
    if column == "created_at":
        return events.to_ist(value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return ""
    text = str(value)
    return "'" + text if text.startswith(FORMULA_START) else text


@router.get("/api/rows.csv", responses={200: {"content": {"text/csv": {}}}, 422: {"model": ErrorBody}})
def rows_csv(from_date: Optional[date] = Query(None, alias="from"), to_date: Optional[date] = Query(None, alias="to")):
    span = _range(from_date, to_date)
    if span is None:
        return _bad_range()
    station = config.STATION["id"]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for row in events.rows_between(station, *span):
        writer.writerow([csv_cell(c, row[c]) for c in CSV_COLUMNS])
    name = f"bolo-line-{station}-{span[0].isoformat()}-to-{span[1].isoformat()}.csv"
    return Response(content="﻿" + out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/api/rows.json", response_model=RowsRangeResponse, responses={422: {"model": ErrorBody}})
def rows_json(from_date: Optional[date] = Query(None, alias="from"), to_date: Optional[date] = Query(None, alias="to")):
    span = _range(from_date, to_date)
    if span is None:
        return _bad_range()
    return {"from_date": span[0].isoformat(), "to_date": span[1].isoformat(),
            "rows": events.rows_between(config.STATION["id"], *span)}
