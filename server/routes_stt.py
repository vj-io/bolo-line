"""STUB owned by package 5 (optional paid engine). Always answers 503 key_not_set."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/api/stt")
def stt():
    return JSONResponse(status_code=503, content={"error": "key_not_set", "message": "SARVAM_API_KEY is not set"})
