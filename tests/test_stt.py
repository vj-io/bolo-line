"""POST /api/stt against a fake Sarvam that answers and fails the way docs.sarvam.ai documents
(speech-to-text reference and errors page, read 27 Nov 2026)."""
import httpx
import pytest
from fastapi.testclient import TestClient

from server import config, stt_sarvam
from server.main import app

client = TestClient(app)
CLIP = (config.WEB_DIR / "samples" / "s1.m4a").read_bytes()


@pytest.fixture
def sarvam(monkeypatch):
    """Sets a fake key and routes Sarvam calls to `answer(request)`; returns the list of requests sent."""
    monkeypatch.setenv("SARVAM_API_KEY", "test-key-not-real")
    sent = []

    def install(answer):
        def handler(request):
            sent.append(request)
            return answer(request)
        monkeypatch.setattr(stt_sarvam, "TRANSPORT", httpx.MockTransport(handler))
        return sent
    return install


def ok(transcript="बैच 14, oven 2, 180 degree, 3 reject"):
    return lambda request: httpx.Response(200, json={
        "request_id": "20261127_00000000-0000-0000-0000-000000000000",
        "transcript": transcript, "language_code": "hi-IN", "language_probability": None,
    })


def form_fields(request):
    """The multipart text fields of a recorded request, as a dict."""
    body = request.content.decode("latin-1")
    out = {}
    for part in body.split("--" + request.headers["content-type"].split("boundary=")[1]):
        if 'name="' in part and "filename=" not in part:
            name = part.split('name="')[1].split('"')[0]
            out[name] = part.split("\r\n\r\n", 1)[1].rsplit("\r\n", 1)[0]
    return out


def post_clip(**data):
    return client.post("/api/stt", files={"file": ("s1.m4a", CLIP, "application/octet-stream")}, data=data)


def audio_files():
    return sorted(p.name for p in (config.data_dir() / "audio").iterdir())


def test_no_key_answers_503_even_with_a_file(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    r = post_clip()
    assert r.status_code == 503
    assert r.json() == {"error": "key_not_set", "message": "SARVAM_API_KEY is not set"}


def test_transcript_is_returned_and_the_clip_is_stored(sarvam):
    sent = sarvam(ok())
    r = post_clip()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"] == "बैच 14, oven 2, 180 degree, 3 reject"
    assert body["engine"] == "sarvam"
    stored = config.data_dir() / body["audio_url"].removeprefix("/")
    assert body["audio_url"].startswith("/audio/") and body["audio_url"].endswith(".m4a")
    assert stored.read_bytes() == CLIP
    assert client.get(body["audio_url"]).content == CLIP
    # What reached Sarvam: the documented URL, header and fields, and the clip itself.
    (req,) = sent
    assert str(req.url) == "https://api.sarvam.ai/speech-to-text"
    assert req.headers["api-subscription-key"] == "test-key-not-real"
    assert form_fields(req) == {"model": "saaras:v4", "mode": "codemix", "language_code": "hi-IN"}
    assert CLIP in req.content and b"audio/mp4" in req.content


def test_language_code_is_passed_through(sarvam):
    sent = sarvam(ok("ஒன்று"))
    r = post_clip(language="ta-IN")
    assert r.status_code == 200
    assert form_fields(sent[0])["language_code"] == "ta-IN"


def test_transcript_whitespace_is_trimmed(sarvam):
    sarvam(ok("  batch 14  "))
    assert post_clip().json()["text"] == "batch 14"


@pytest.mark.parametrize("status, body, expect", [
    (403, {"error": {"message": "Invalid API key", "code": "invalid_api_key_error", "request_id": "r1"}}, "Invalid API key"),
    (402, {"error": {"message": "No credits available.", "code": "insufficient_quota_error"}}, "No credits available."),
    (400, {"error": {"message": "Audio duration exceeds the maximum limit of 30 seconds", "code": "invalid_request_error"}}, "30 seconds"),
    (400, {"detail": "Model saaras:v2.5 is deprecated"}, "deprecated"),
    (429, {"error": {"message": "Rate limit exceeded", "code": "rate_limit_exceeded_error"}}, "Rate limit exceeded"),
    (503, {"error": {"message": "Model overloaded", "code": "model_overloaded"}}, "Model overloaded"),
])
def test_provider_errors_become_502_with_the_provider_message(sarvam, status, body, expect):
    sarvam(lambda request: httpx.Response(status, json=body))
    before = audio_files()
    r = post_clip()
    assert r.status_code == 502, r.text
    assert r.json()["error"] == "stt_failed"
    assert f"Sarvam answered {status}" in r.json()["message"] and expect in r.json()["message"]
    assert audio_files() == before  # a failed clip is not kept


def test_non_json_error_and_missing_transcript_are_failures(sarvam):
    sarvam(lambda request: httpx.Response(500, text="upstream exploded"))
    assert post_clip().json() == {"error": "stt_failed", "message": "Sarvam answered 500: upstream exploded"}
    sarvam(lambda request: httpx.Response(200, json={"request_id": "r2"}))
    assert post_clip().json() == {"error": "stt_failed", "message": "Sarvam answered 200 without a transcript"}


def test_network_failure_is_a_502(sarvam):
    def down(request):
        raise httpx.ConnectError("no route", request=request)
    sarvam(down)
    r = post_clip()
    assert r.status_code == 502
    assert r.json()["message"] == "Sarvam could not be reached: ConnectError"
    assert "test-key-not-real" not in r.text


def test_bad_uploads_are_refused_before_sarvam_is_called(sarvam, monkeypatch):
    sent = sarvam(ok())
    r = client.post("/api/stt")
    assert r.status_code == 400 and r.json()["error"] == "invalid_request" and "required" in r.json()["message"]
    r = client.post("/api/stt", files={"file": ("x.m4a", b"", "audio/mp4")})
    assert r.status_code == 400 and "empty" in r.json()["message"]
    r = client.post("/api/stt", files={"file": ("page.html", b"<script>", "text/html")})
    assert r.status_code == 400 and "unsupported audio type text/html" in r.json()["message"]
    monkeypatch.setattr("server.routes_stt.MAX_BYTES", 10)
    r = client.post("/api/stt", files={"file": ("x.m4a", b"x" * 11, "audio/mp4")})
    assert r.status_code == 413 and r.json()["error"] == "file_too_large"
    assert client.post("/api/stt", files={"file": ("x.m4a", b"x" * 10, "audio/mp4")}).status_code == 200
    assert len(sent) == 1


def test_browser_recording_type_picks_the_extension(sarvam):
    sent = sarvam(ok())
    r = client.post("/api/stt", files={"file": ("speech", b"webm-bytes", "audio/webm;codecs=opus")})
    assert r.status_code == 200 and r.json()["audio_url"].endswith(".webm")
    assert b'filename="' in sent[0].content and b"Content-Type: audio/webm" in sent[0].content


def test_config_still_reports_the_engine(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test-key-not-real")
    assert client.get("/api/config").json()["engines"]["sarvam"] == {"configured": True, "message": "ready"}
