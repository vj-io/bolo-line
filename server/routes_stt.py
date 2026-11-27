"""POST /api/stt: one recording (multipart `file`, plus an optional BCP-47 `language`) to Sarvam."""
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from . import budget, config, stt_sarvam
from .contracts import SttResponse

router = APIRouter()

# ponytail: a byte cap stands in for the 15 s cap, since reading a duration needs an audio decoder.
# The recorder stops at 15 s (web/station/speech.js) and Sarvam refuses anything over 30 s.
MAX_BYTES = 5 * 1024 * 1024
# Stored clips are served from /audio, so the extension comes from this list, never from the upload.
EXTENSIONS = {
    "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a",
    "audio/aac": ".aac", "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav",
}
TYPES = {ext: mime for mime, ext in reversed(EXTENSIONS.items())}  # first listed type wins: .m4a -> audio/mp4


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def key_not_set() -> JSONResponse:
    return error(503, "key_not_set", "SARVAM_API_KEY is not set")


def budget_reached(what: str) -> JSONResponse:
    return error(503, "budget_reached", f"Today's Sarvam {what} limit is used up. It starts again at midnight IST.")


@router.post("/api/stt", response_model=SttResponse)
def stt(file: Optional[UploadFile] = File(None), language: str = Form("hi-IN")):
    if not config.sarvam_key():
        return key_not_set()
    if file is None:
        return error(400, "invalid_request", "file: a recording is required")
    mime = (file.content_type or "").split(";")[0].strip().lower()
    ext = EXTENSIONS.get(mime) or Path(file.filename or "").suffix.lower()
    if ext not in TYPES:
        return error(400, "invalid_request", f"file: unsupported audio type {mime or 'unknown'}")
    audio = file.file.read(MAX_BYTES + 1)
    if not audio:
        return error(400, "invalid_request", "file: the recording is empty")
    if len(audio) > MAX_BYTES:
        return error(413, "file_too_large", f"file: recordings are capped at {MAX_BYTES // (1024 * 1024)} MB")
    name = f"{uuid.uuid4().hex}{ext}"
    try:
        budget.spend(budget.STT_CALLS, 1)  # counted when sent, whatever Sarvam answers
        text = stt_sarvam.transcribe(audio, name, TYPES[ext], language)
    except budget.BudgetReached:
        return budget_reached("speech-to-text")
    except stt_sarvam.SarvamError as exc:
        return error(502, "stt_failed", str(exc))
    (config.data_dir() / "audio" / name).write_bytes(audio)
    return SttResponse(text=text, engine="sarvam", audio_url=f"/audio/{name}")
