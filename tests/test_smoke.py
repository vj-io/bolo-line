from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_config_without_key(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    body = client.get("/api/config").json()
    assert body["station"]["id"] == "oven-line"
    assert body["engines"]["sarvam"] == {"configured": False, "message": "key not set"}
    assert [s["id"] for s in body["samples"]] == ["s1", "s2", "s3", "s3b", "s4"]
    assert body["prompts"]["saved"]["roman"] == "Save ho gaya"


def test_pages_and_assets():
    for path in ("/", "/dashboard", "/demo", "/shared/tokens.css", "/shared/base.css",
                 "/shared/sketch.js", "/vendor/rough.esm.js", "/samples/s1.m4a"):
        assert client.get(path).status_code == 200, path


def test_stt_without_key():
    r = client.post("/api/stt")
    assert r.status_code == 503 and r.json()["error"] == "key_not_set"
