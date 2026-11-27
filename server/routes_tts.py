"""POST /api/tts: {"text", "language"} to Sarvam's voice; answers the WAV bytes (audio/wav)."""
from fastapi import APIRouter
from fastapi.responses import Response

from . import config, tts_sarvam
from .contracts import TtsRequest
from .routes_stt import error, key_not_set
from .stt_sarvam import SarvamError

router = APIRouter()


@router.post("/api/tts")
def tts(req: TtsRequest):
    if not config.sarvam_key():
        return key_not_set()
    try:
        audio = tts_sarvam.synthesize(req.text, req.language)
    except SarvamError as exc:
        return error(502, "tts_failed", str(exc))
    return Response(content=audio, media_type=tts_sarvam.MEDIA_TYPE)
