"""The daily Sarvam caps (server/budget.py) through /api/stt and /api/tts, against a fake Sarvam; plus the .m4a media
type of the sample clips (T12)."""
import base64
import json
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from server import budget, config, db, stt_sarvam, tts_sarvam
from server.main import app

client = TestClient(app)
CLIP = (config.WEB_DIR / "samples" / "s1.m4a").read_bytes()
READBACK = "बैच 14, ओवन 2, 180 डिग्री, 3 रिजेक्ट। सही है?"
SAVED = "सेव हो गया"
AGAIN = "फिर से बोलिए"


@pytest.fixture
def clock(monkeypatch):
    """Sets the server's clock with clock("2026-11-27 18:30:00"), a UTC time. Starts at 27 Nov 12:00 IST."""
    now = {}

    def set_utc(text):
        now["t"] = datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
    set_utc("2026-11-27 06:30:00")
    monkeypatch.setattr(db, "now", lambda: now["t"])
    return set_utc


@pytest.fixture
def sarvam(monkeypatch, clock):
    """A fake key, no limits set, fresh counters, an empty voice cache, and a fake Sarvam that answers both endpoints
    (the voice's audio is the phrase's own bytes). Returns the list of requests that reached Sarvam."""
    monkeypatch.setenv("SARVAM_API_KEY", "test-key-not-real")
    monkeypatch.delenv(budget.STT_CALLS, raising=False)
    monkeypatch.delenv(budget.TTS_CHARS, raising=False)
    monkeypatch.setattr(budget, "_day", None)
    monkeypatch.setattr(budget, "_used", {})
    tts_sarvam.synthesize.cache_clear()
    sent = []

    def answer(request):
        sent.append(request)
        if request.url.path == "/speech-to-text":
            return httpx.Response(200, json={"request_id": "r", "transcript": "batch 14"})
        audio = json.loads(request.content)["text"].encode()
        return httpx.Response(200, json={"request_id": "r", "audios": [base64.b64encode(audio).decode()]})
    monkeypatch.setattr(stt_sarvam, "TRANSPORT", httpx.MockTransport(answer))
    yield sent
    tts_sarvam.synthesize.cache_clear()


def stt():
    return client.post("/api/stt", files={"file": ("s1.m4a", CLIP, "audio/mp4")})


def tts(text):
    return client.post("/api/tts", json={"text": text})


def test_stt_limit_holds_at_its_edge(sarvam, monkeypatch):
    monkeypatch.setenv(budget.STT_CALLS, "2")
    assert stt().status_code == 200
    assert stt().status_code == 200  # the last allowed call
    r = stt()
    assert r.status_code == 503
    assert r.json() == {"error": "budget_reached",
                        "message": "Today's Sarvam speech-to-text limit is used up. It starts again at midnight IST."}
    assert len(sarvam) == 2  # the refused call never reached Sarvam


def test_stt_counts_a_call_when_it_is_sent(sarvam, monkeypatch):
    monkeypatch.setenv(budget.STT_CALLS, "1")
    # Refused before sending: free.
    assert client.post("/api/stt", files={"file": ("x.m4a", b"", "audio/mp4")}).status_code == 400
    # Sent, so counted, although Sarvam failed.
    monkeypatch.setattr(stt_sarvam, "TRANSPORT", httpx.MockTransport(
        lambda request: httpx.Response(402, json={"error": {"message": "No credits available."}})))
    assert stt().status_code == 502
    assert stt().json()["error"] == "budget_reached"


def test_the_count_starts_again_at_midnight_ist(sarvam, clock, monkeypatch):
    monkeypatch.setenv(budget.STT_CALLS, "1")
    clock("2026-11-27 18:29:58")  # 23:59:58 IST, 27 Nov
    assert stt().status_code == 200
    clock("2026-11-27 18:29:59")  # 23:59:59 IST, the same day
    assert stt().status_code == 503
    clock("2026-11-27 18:30:00")  # 00:00:00 IST, 28 Nov
    assert stt().status_code == 200
    clock("2026-11-28 00:00:00")  # UTC midnight is 05:30 IST: still 28 Nov
    assert stt().status_code == 503
    assert len(sarvam) == 2


def test_tts_limit_holds_at_its_edge_and_a_cached_phrase_costs_nothing(sarvam, monkeypatch):
    monkeypatch.setenv(budget.TTS_CHARS, str(len(READBACK) + len(SAVED)))
    assert tts(READBACK).status_code == 200
    assert tts(READBACK).status_code == 200  # served from the cache, so it costs nothing...
    assert tts(SAVED).status_code == 200  # ...and this phrase still fits, exactly at the limit
    r = tts(AGAIN)
    assert r.status_code == 503
    assert r.json() == {"error": "budget_reached",
                        "message": "Today's Sarvam voice limit is used up. It starts again at midnight IST."}
    assert tts(READBACK).content == READBACK.encode()  # a cached phrase is still served once the limit is reached
    assert [json.loads(req.content)["text"] for req in sarvam] == [READBACK, SAVED]


def test_a_refused_phrase_is_not_cached_and_succeeds_after_midnight_ist(sarvam, clock, monkeypatch):
    monkeypatch.setenv(budget.TTS_CHARS, str(len(AGAIN)))  # AGAIN fits a fresh day, not one SAVED has started
    clock("2026-11-27 18:29:59")  # 23:59:59 IST, 27 Nov
    assert tts(SAVED).status_code == 200
    assert tts(AGAIN).status_code == 503
    clock("2026-11-27 18:30:00")  # 00:00:00 IST, 28 Nov
    assert tts(AGAIN).content == AGAIN.encode()
    assert [json.loads(req.content)["text"] for req in sarvam] == [SAVED, AGAIN]


def test_unset_or_empty_means_no_limit(sarvam, monkeypatch):
    monkeypatch.setenv(budget.STT_CALLS, "")
    for _ in range(3):
        assert stt().status_code == 200
        assert tts(f"{AGAIN} {_}").status_code == 200
    assert len(sarvam) == 6


def test_m4a_clips_are_served_as_audio_mp4():
    r = client.get("/samples/s1.m4a")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mp4"
