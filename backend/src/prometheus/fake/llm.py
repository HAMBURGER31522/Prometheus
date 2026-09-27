"""A fake model endpoint for the settings E2E (PLAN 15.4.8, E11): 「获取模型列表」 is exercised
against the fake backend itself, so no test ever reaches a real provider or relay."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/fake-llm/v1/models")
async def models():
    return {"object": "list", "data": [{"id": "fake-model-a"}, {"id": "fake-model-b"}]}
