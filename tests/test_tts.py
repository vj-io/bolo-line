"""POST /api/tts against a fake Sarvam that answers and fails the way docs.sarvam.ai documents
(text-to-speech reference and errors page, read 27 Nov 2026)."""
import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from server import stt_sarvam, tts_sarvam
from server.main import app

client = TestClient(app)
WAV = b"RIFF$\x00\x00\x00WAVEfmt fake-wav-bytes"
READBACK = "बैच 14, ओवन 2, 180 डिग्री, 3 रिजेक्ट। सही है?"


@pytest.fixture
def sarvam(monkeypatch):
    """Sets a fake key, empties the voice cache, and routes Sarvam calls to `answer(request)`."""
    monkeypatch.setenv("SARVAM_API_KEY", "test-key-not-real")
    tts_sarvam.synthesize.cache_clear()
    sent = []

    def install(answer):
        def handler(request):
            sent.append(request)
            return answer(request)
        monkeypatch.setattr(stt_sarvam, "TRANSPORT", httpx.MockTransport(handler))
        return sent
    yield install
    tts_sarvam.synthesize.cache_clear()


def speaks(request):
    """Answers with audio that names the request's text, so each phrase gets distinct bytes."""
    text = json.loads(request.content)["text"]
    audio = WAV + text.encode()
    return httpx.Response(200, json={"request_id": "20261127_x", "audios": [base64.b64encode(audio).decode()]})


def say(text=READBACK, **extra):
    return client.post("/api/tts", json={"text": text, **extra})


def test_no_key_answers_503(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    r = say()
    assert r.status_code == 503
    assert r.json() == {"error": "key_not_set", "message": "SARVAM_API_KEY is not set"}


def test_audio_comes_back_as_wav(sarvam):
    sent = sarvam(speaks)
    r = say()
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "audio/wav"
    assert r.content == WAV + READBACK.encode()
    (req,) = sent
    assert str(req.url) == "https://api.sarvam.ai/text-to-speech"
    assert req.headers["api-subscription-key"] == "test-key-not-real"
    assert json.loads(req.content) == {
        "text": READBACK, "language_code": "hi-IN", "model": "bulbul:v4-flash",
        "speaker": "aparna_hi_customer", "pace": 0.9, "enable_preprocessing": True,
    }


def test_a_language_without_a_chosen_voice_uses_the_model_default(sarvam):
    sent = sarvam(speaks)
    assert say("ஒன்று", language="ta-IN").status_code == 200
    body = json.loads(sent[0].content)
    assert body["language_code"] == "ta-IN" and "speaker" not in body


def test_identical_requests_are_billed_once(sarvam):
    sent = sarvam(speaks)
    first = say().content
    assert say().content == first
    assert say("  " + READBACK + " ").content == first  # surrounding spaces do not make a new phrase
    assert len(sent) == 1
    # Each part of the cache key matters: another text, or another language, is a new call.
    assert say("सेव हो गया").content == WAV + "सेव हो गया".encode()
    say(READBACK, language="mr-IN")
    assert len(sent) == 3


@pytest.mark.parametrize("status, body, expect", [
    (403, {"error": {"message": "Invalid API key", "code": "invalid_api_key_error", "request_id": "r1"}}, "Invalid API key"),
    (400, {"error": {"message": "Speaker ritu is not valid for bulbul:v4-flash", "code": "invalid_request_error"}}, "not valid"),
    (402, {"error": {"message": "No credits available.", "code": "insufficient_quota_error"}}, "No credits available."),
    (429, {"error": {"message": "Rate limit exceeded", "code": "rate_limit_exceeded_error"}}, "Rate limit exceeded"),
])
def test_provider_errors_become_502_and_are_not_cached(sarvam, status, body, expect):
    sent = sarvam(lambda request: httpx.Response(status, json=body))
    r = say()
    assert r.status_code == 502, r.text
    assert r.json()["error"] == "tts_failed"
    assert f"Sarvam answered {status}" in r.json()["message"] and expect in r.json()["message"]
    sarvam(speaks)
    assert say().status_code == 200  # the failure was not remembered
    assert len(sent) == 2


@pytest.mark.parametrize("body, expect", [
    ({"request_id": "r", "audios": []}, "without audio"),
    ({"request_id": "r"}, "without audio"),
    ({"request_id": "r", "audios": ["not base64!"]}, "not valid base64"),
])
def test_malformed_success_is_a_failure(sarvam, body, expect):
    sarvam(lambda request: httpx.Response(200, json=body))
    r = say()
    assert r.status_code == 502 and expect in r.json()["message"]


def test_bad_requests_are_refused_before_sarvam_is_called(sarvam):
    sent = sarvam(speaks)
    assert say("   ").status_code == 422
    assert say("क" * 501).status_code == 422
    assert say(language="hindi").status_code == 422
    assert say("क" * 500).status_code == 200
    assert len(sent) == 1
