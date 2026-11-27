"""Sarvam speech-to-text, plus the HTTP call shared with tts_sarvam.py.

Facts read from docs.sarvam.ai on 27 Nov 2026 (re-check before changing):
- POST https://api.sarvam.ai/speech-to-text, multipart, header `api-subscription-key`.
- `saaras:v4` is the default, recommended model; `saaras:v3` is legacy.
- Modes: transcribe (default), translate, verbatim, translit, codemix. `keyterms` (saaras:v4 only)
  takes up to 50 words to listen for, as a JSON array in one form field.
- Chosen by running the five sample clips on 27 Nov 2026 (parsed fields right, of 5):
  codemix 1, translit 2, verbatim 3, transcribe 3; with the station's words as keyterms,
  verbatim 4 and transcribe 5. Without keyterms "batch" came back as "ब्याज" and adjacent numbers
  were glued ("oven do, chaar reject" -> "oven 24 reject").
- Up to 30 s of audio per request; WAV, MP3, AAC, M4A, OGG/Opus, WebM and more are accepted.
- Success: {"request_id", "transcript", "language_code", ...}.
  Errors: {"error": {"message", "code", "request_id"}}, or {"detail": "..."} for a bad model.
"""
import json

import httpx

from . import config

BASE_URL = "https://api.sarvam.ai"
MODEL = "saaras:v4"
MODE = "transcribe"
# The words every record uses: field keywords, machine types and names ("Oven 2").
KEYTERMS = ["batch", "reject", "degree"] + sorted({m["type"] for m in config.STATION["machines"]}) + [
    m["name"] for m in config.STATION["machines"]]
TIMEOUT_S = 30
# Tests swap in httpx.MockTransport here; None means the real network.
TRANSPORT = None


class SarvamError(Exception):
    """The provider failed or answered with an error; the message is safe to show (no key in it)."""


def post(path: str, **kwargs) -> dict:
    """POSTs to Sarvam with the key header and returns the JSON body, or raises SarvamError."""
    headers = {"api-subscription-key": config.sarvam_key()}
    try:
        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT_S, transport=TRANSPORT) as client:
            r = client.post(path, headers=headers, **kwargs)
    except httpx.HTTPError as exc:
        raise SarvamError(f"Sarvam could not be reached: {type(exc).__name__}") from exc
    try:
        body = r.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        body = {}  # callers then report the missing transcript or audio
    if r.status_code != 200:
        err = body.get("error")
        detail = err.get("message") if isinstance(err, dict) else body.get("detail")
        raise SarvamError(f"Sarvam answered {r.status_code}: {detail or r.text[:200] or 'no detail'}")
    return body


def transcribe(audio: bytes, filename: str, content_type: str, language: str = "hi-IN") -> str:
    """Returns the transcript of one short clip. `language` is a BCP-47 code such as hi-IN."""
    body = post(
        "/speech-to-text",
        files={"file": (filename, audio, content_type)},
        data={"model": MODEL, "mode": MODE, "language_code": language, "keyterms": json.dumps(KEYTERMS)},
    )
    text = body.get("transcript")
    if not isinstance(text, str):
        raise SarvamError("Sarvam answered 200 without a transcript")
    return text.strip()
