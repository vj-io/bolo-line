"""Pydantic models for every request and response in PRD section 3.4. Frozen: change only through the integrator."""
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, StringConstraints

FieldName = Literal["batch_no", "machine", "temperature_c", "rejects"]
Source = Literal["mic_browser", "mic_sarvam", "sample", "typed", "seed"]


class ErrorBody(BaseModel):
    error: str
    message: str


class Fields(BaseModel):
    batch_no: Optional[int] = None
    machine: Optional[str] = None
    temperature_c: Optional[int] = None
    rejects: Optional[int] = None


class Say(BaseModel):
    hi: str
    roman: str


class Flags(BaseModel):
    temp_out_of_limit: bool = False
    rejects_over_limit: bool = False


class Problem(BaseModel):
    field: FieldName
    value: Union[int, str]
    reason: Literal["impossible", "unknown_machine"]


class Suggest(BaseModel):
    field: Literal["machine"] = "machine"
    value: str


class ParseRequest(BaseModel):
    station_id: str
    text: str = ""
    draft: Optional[Fields] = None
    expect: Optional[FieldName] = None


class ParseResponse(BaseModel):
    status: Literal["complete", "need_field", "confirm_machine", "not_understood", "no_speech"]
    fields: Fields
    ask: Optional[FieldName] = None
    suggest: Optional[Suggest] = None
    problems: list[Problem] = []
    flags: Flags = Flags()
    say: Say


class ConfirmRequest(BaseModel):
    text: str = ""


class ConfirmResponse(BaseModel):
    answer: Literal["yes", "no", "unclear"]


class RowIn(BaseModel):
    station_id: str
    batch_no: int
    machine: str
    temperature_c: int
    rejects: int
    transcript: str = ""
    source: Source
    audio_url: Optional[str] = None


class Row(BaseModel):
    id: int
    created_at: str  # ISO 8601 UTC, e.g. 2026-11-28T09:15:02Z
    station_id: str
    station_name: str
    operator: str
    batch_no: int
    machine: str
    temperature_c: int
    rejects: int
    temp_out_of_limit: bool
    rejects_over_limit: bool
    transcript: str
    source: Source
    audio_url: Optional[str] = None


class RowsResponse(BaseModel):
    rows: list[Row]  # newest first
    server_time: str


class SttResponse(BaseModel):
    text: str
    engine: Literal["sarvam"]
    audio_url: Optional[str] = None


class TtsRequest(BaseModel):
    """POST /api/tts (package 5). The reply is the audio itself (audio/wav), not JSON."""
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    language: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}-[A-Z]{2}$")] = "hi-IN"  # BCP-47


# ---- Package 7: first-try events, stats with the end-of-shift summary, audit export ----
Engine = Literal["browser", "sarvam", "sample", "typed"]


class EventIn(BaseModel):
    """POST /api/events: one finished attempt, sent by the operator screen after a save or a discard."""
    kind: Literal["saved", "discarded"]
    first_try: bool
    engine: Engine
    lang: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}-[A-Z]{2}$")]  # BCP-47
    station_id: str


class Tally(BaseModel):
    attempts: int
    saved: int
    first_try: int
    discarded: int
    first_try_share: Optional[float] = None  # first_try / attempts; null when there are no attempts


class OutOfLimit(BaseModel):
    batch_no: int
    machine: str
    field: Literal["temperature_c", "rejects"]
    value: int


class ShiftSummary(BaseModel):
    batches: int
    out_of_limit: list[OutOfLimit]  # oldest first; a row with both flags appears twice
    rejects_by_machine: dict[str, int]  # every machine of the station, in station order
    last_log_at: Optional[str] = None  # ISO 8601 UTC


class StatsResponse(BaseModel):
    """GET /api/stats?date=YYYY-MM-DD: one day in Asia/Kolkata."""
    date: str
    station_id: str
    total: Tally
    by_engine: dict[str, Tally]
    by_lang: dict[str, Tally]
    shift: ShiftSummary


class RowsRangeResponse(BaseModel):
    """GET /api/rows.json?from=&to=: the rows behind the CSV and the print view, oldest first."""
    from_date: str
    to_date: str
    rows: list[Row]
