"""Sarvam text-to-speech for the read-back and the prompts.

Facts read from docs.sarvam.ai on 27 Nov 2026 (re-check before changing):
- POST https://api.sarvam.ai/text-to-speech, JSON {"text", "language_code", "model", "speaker", ...},
  header `api-subscription-key`; text up to 2,500 characters.
- `bulbul:v4-flash` is the latest, recommended model (₹2 per 1,000 characters, pay as you go);
  `bulbul:v3` is the API default (₹3). Speaker names are model-specific.
- Success: {"request_id", "audios": ["<base64>"]}; the audio is WAV unless output_audio_codec says otherwise.
"""
import base64
import binascii
from functools import lru_cache

from . import budget
from .stt_sarvam import SarvamError, post

MODEL = "bulbul:v4-flash"
MEDIA_TYPE = "audio/wav"
# Voice per BCP-47 code (docs: "always pass speaker explicitly"). aparna_hi_customer is the docs'
# first-ranked Hindi voice for customer care. A code without an entry gets the model's default voice.
SPEAKERS = {"hi-IN": "aparna_hi_customer"}
# Calibration knob: the docs suggest 0.8 to 0.9 for instructions; 1.0 is their conversational default.
PACE = 0.9


# ponytail: in-process LRU, so each server worker bills a phrase once; a shared cache only matters with many workers.
@lru_cache(maxsize=256)
def synthesize(text: str, language: str = "hi-IN") -> bytes:
    """Returns WAV bytes for `text` spoken in `language` (a BCP-47 code). Errors are not cached."""
    # enable_preprocessing reads digits as words ("बैच 14" in the read-back).
    payload = {"text": text, "language_code": language, "model": MODEL, "pace": PACE, "enable_preprocessing": True}
    if language in SPEAKERS:
        payload["speaker"] = SPEAKERS[language]
    budget.spend(budget.TTS_CHARS, len(text))  # only a cache miss gets here; BudgetReached is not cached either
    body = post("/text-to-speech", json=payload)
    audios = body.get("audios")
    if not isinstance(audios, list) or not audios or not isinstance(audios[0], str):
        raise SarvamError("Sarvam answered 200 without audio")
    try:
        return base64.b64decode(audios[0], validate=True)
    except binascii.Error as exc:
        raise SarvamError("Sarvam audio was not valid base64") from exc
