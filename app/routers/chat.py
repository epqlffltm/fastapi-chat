#app/routers/chat.py

'''
2026-07-11
GET /models, POST /chat

2026-07-11
챗봇 서버 - Pydantic 스키마 정의(app/schemas.py)로 이동
'''

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.config import OLLAMA_TAGS_URL, SYSTEM_PROMPT
from app.ollama_client import get_default_model, ollama_stream
from app.schemas import ChatMessage, ChatRequest

router = APIRouter()

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    think: bool = False

@router.get("/models")
async def list_models():
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(OLLAMA_TAGS_URL)
        data = response.json()
    return {"models": [m["name"] for m in data.get("models", [])]}

@router.post("/chat")
async def chat(payload: ChatRequest):
    model = payload.model or await get_default_model()

    ollama_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    ollama_messages += [{"role": m.role, "content": m.content} for m in payload.messages]

    return StreamingResponse(
        ollama_stream(model, ollama_messages, payload.think),
        media_type="application/x-ndjson; charset=utf-8",
    )