from fastapi import APIRouter

from . import config

router = APIRouter()
VERSION = "0.1.0"


@router.get("/api/health")
def health():
    return {"status": "ok", "version": VERSION}


@router.get("/api/config")
def get_config():
    configured = bool(config.sarvam_key())
    return {
        "station": config.STATION,
        "engines": {
            "browser": {"label": "Browser speech (no key)"},
            "sarvam": {"configured": configured, "message": "ready" if configured else "key not set"},
        },
        "samples": config.SAMPLES,
        "prompts": config.PROMPTS,
        # One entry per language pack, the default (Hindi) first. `samples` are that language's own
        # tester samples; the top-level `samples` above stay the Hindi ones.
        "languages": [
            {**{k: pack[k] for k in ("code", "locale", "name", "name_en", "status", "labels", "prompts")},
             "samples": [{**s, "lang": pack["code"]} for s in pack["samples"]]}
            for pack in config.LANGS.values()
        ],
    }
