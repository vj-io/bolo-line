"""STUB owned by package 1 (parser). Answers every parse with test-table row 1 and every confirm with yes."""
from fastapi import APIRouter

from .contracts import ConfirmRequest, ConfirmResponse, Fields, Flags, ParseRequest, ParseResponse, Say

router = APIRouter()


@router.post("/api/parse", response_model=ParseResponse)
def parse(req: ParseRequest):
    return ParseResponse(
        status="complete",
        fields=Fields(batch_no=14, machine="Oven 2", temperature_c=180, rejects=3),
        flags=Flags(),
        say=Say(hi="बैच 14, ओवन 2, 180 डिग्री, 3 रिजेक्ट। सही है?",
                roman="Batch 14, Oven 2, 180 degree, 3 reject. Sahi hai?"),
    )


@router.post("/api/confirm", response_model=ConfirmResponse)
def confirm(req: ConfirmRequest):
    return ConfirmResponse(answer="yes")
