"""`POST /api/parse` and `POST /api/confirm` (PRD 3.4). The rules live in server/parser."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from . import config, parser
from .contracts import ConfirmRequest, ConfirmResponse, ErrorBody, ParseRequest, ParseResponse

router = APIRouter()


def _unknown(what: str, value: str):
    return JSONResponse(status_code=404, content={"error": f"unknown_{what}", "message": f"No {what} with id {value!r}"})


@router.post("/api/parse", response_model=ParseResponse, response_model_exclude_unset=True,
             responses={404: {"model": ErrorBody}})
def parse(req: ParseRequest):
    station = config.get_station(req.station_id)
    if station is None:
        return _unknown("station", req.station_id)
    if config.get_lang(req.lang) is None:
        return _unknown("language", req.lang)
    draft = req.draft.model_dump() if req.draft else None
    body = parser.parse(req.text, station, draft=draft, expect=req.expect, lang=req.lang)
    if "lang" not in req.model_fields_set:
        # A caller written before the language packs sends no `lang` and gets exactly the old body:
        # no `hint`, and `say` with `hi` and `roman` only.
        del body["hint"]
        body["say"] = {k: body["say"][k] for k in ("hi", "roman")}
    return body


@router.post("/api/confirm", response_model=ConfirmResponse, responses={404: {"model": ErrorBody}})
def confirm(req: ConfirmRequest):
    if config.get_lang(req.lang) is None:
        return _unknown("language", req.lang)
    return ConfirmResponse(answer=parser.confirm(req.text, req.lang))
