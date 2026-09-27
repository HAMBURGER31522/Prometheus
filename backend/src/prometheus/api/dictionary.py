"""Hover lookup endpoints for English subtitles (PLAN 15.4.9)."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/dictionary")
async def status():
    return {"state": "idle", "detail": ""}


@router.post("/api/dictionary/install")
async def install():
    return {"started": False}


@router.get("/api/dictionary/lookup")
async def lookup(word: str):
    return JSONResponse({"code": "WORD_NOT_FOUND"}, status_code=404)
