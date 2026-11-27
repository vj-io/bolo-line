"""Pydantic models for every request and response in PRD section 3.4. Frozen: change only through the integrator."""
from typing import Literal, Optional, Union

from pydantic import BaseModel

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
    text: Optional[str] = None  # the words to speak, in the script of `lang`; `hi` is its old name and holds the same
    lang: Optional[str] = None  # locale of `text`, e.g. "mr-IN". Both are sent when the request names a `lang`.


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
    lang: str = "hi"  # a language pack code from /api/config `languages`


class ParseResponse(BaseModel):
    status: Literal["complete", "need_field", "confirm_machine", "not_understood", "no_speech"]
    fields: Fields
    ask: Optional[FieldName] = None
    suggest: Optional[Suggest] = None
    problems: list[Problem] = []
    flags: Flags = Flags()
    say: Say
    hint: Optional[Literal["wrong_language"]] = None  # sent when the request names a `lang`


class ConfirmRequest(BaseModel):
    text: str = ""
    lang: str = "hi"


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
