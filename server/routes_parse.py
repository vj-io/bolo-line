"""`POST /api/parse` and `POST /api/confirm` (PRD 3.4). The rules live in server/parser."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from . import config, parser
from .contracts import ConfirmRequest, ConfirmResponse, ErrorBody, ParseRequest, ParseResponse

router = APIRouter()


@router.post("/api/parse", response_model=ParseResponse, responses={404: {"model": ErrorBody}})
def parse(req: ParseRequest):
    station = config.get_station(req.station_id)
    if station is None:
        return JSONResponse(status_code=404, content={"error": "unknown_station",
                                                      "message": f"No station with id {req.station_id!r}"})
    draft = req.draft.model_dump() if req.draft else None
    return parser.parse(req.text, station, config.PROMPTS, draft, req.expect)


@router.post("/api/confirm", response_model=ConfirmResponse)
def confirm(req: ConfirmRequest):
    return ConfirmResponse(answer=parser.confirm(req.text))
