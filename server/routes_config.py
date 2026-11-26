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
    }
