import json
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import MAX_HISTORY, OLLAMA_TAGS_URL, SYSTEM_PROMPT
from app.database.database import get_db
from app.database.models import ChatMessage, ChatSession
from app.ollama_client import get_default_model, ollama_stream
from app.schemas import ChatRequest

router = APIRouter()


@router.get("/models")
async def list_models():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(OLLAMA_TAGS_URL)
            response.raise_for_status()
    except httpx.ConnectError as exc:
        raise HTTPException(
            status_code=503,
            detail="Ollama 서버에 연결할 수 없습니다. Ollama가 실행 중인지 확인해주세요.",
        ) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Ollama 서버 응답 시간이 초과되었습니다.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama 서버가 오류를 반환했습니다. (status {exc.response.status_code})",
        ) from exc

    data = response.json()
    return {"models": [model["name"] for model in data.get("models", [])]}


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
    ollama_messages += [{"role": message.role, "content": message.content} for message in history]

    async def stream_and_save():
        full_text = ""
        stream_failed = False

        async for chunk in ollama_stream(model, ollama_messages, payload.think):
            try:
                event = json.loads(chunk)
                if event.get("type") == "content":
                    full_text += event["text"]
                elif event.get("type") == "error":
                    stream_failed = True
            except json.JSONDecodeError:
                stream_failed = True

            yield chunk

        if full_text and not stream_failed:
            db.add(ChatMessage(session_id=payload.session_id, role="assistant", content=full_text))
            session.updated_at = datetime.now(timezone.utc)
            db.commit()

    return StreamingResponse(
        stream_and_save(),
        media_type="application/x-ndjson; charset=utf-8",
    )
