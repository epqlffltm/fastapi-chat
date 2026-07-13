#app/routers/chat.py

'''
2026-07-11
GET /models, POST /chat

2026-07-11
챗봇 서버 - Pydantic 스키마 정의(app/schemas.py)로 이동
스키마 정의 제거, import로 교체
'''

import json
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.config import OLLAMA_TAGS_URL, SYSTEM_PROMPT, MAX_HISTORY
from app.database.database import get_db
from app.database.models import ChatSession, ChatMessage
from app.ollama_client import get_default_model, ollama_stream
from app.schemas import ChatRequest

router = APIRouter()

@router.get("/models")
async def list_models():
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(OLLAMA_TAGS_URL)
        data = response.json()
    return {"models": [m["name"] for m in data.get("models", [])]}

@router.post("/chat")
async def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == payload.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    model = payload.model or session.model or await get_default_model()

    if not payload.regenerate:
        if not payload.message:
            raise HTTPException(status_code=400, detail="message가 필요합니다.")
        db.add(ChatMessage(session_id=payload.session_id, role="user", content=payload.message))
        if session.title == "새 대화":
            session.title = payload.message[:20] + ("…" if len(payload.message) > 20 else "")
        db.commit()

    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == payload.session_id)
        .order_by(ChatMessage.id.desc())
        .limit(MAX_HISTORY)
        .all()
    )
    history.reverse()

    ollama_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    ollama_messages += [{"role": m.role, "content": m.content} for m in history]

    async def stream_and_save():
        full_text = ""
        async for chunk in ollama_stream(model, ollama_messages, payload.think):
            try:
                evt = json.loads(chunk)
                if evt.get("type") == "content":
                    full_text += evt["text"]
            except json.JSONDecodeError:
                pass
            yield chunk

        if full_text:
            db.add(ChatMessage(session_id=payload.session_id, role="assistant", content=full_text))
            session.updated_at = datetime.now(timezone.utc)
            db.commit()

    return StreamingResponse(
        stream_and_save(),
        media_type="application/x-ndjson; charset=utf-8",
    )