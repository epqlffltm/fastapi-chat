#app/routers/chat.py

'''
2026-07-11
GET /models, POST /chat

2026-07-11
챗봇 서버 - Pydantic 스키마 정의(app/schemas.py)로 이동
스키마 정의 제거, import로 교체

2026-07-14
Ollama가 꺼져있을 때 앱이 죽는 버그 수정
비동기 수정
비동기 SQLAlchemy 적용 + Ollama 연결 실패 처리
토큰 기반 히스토리 관리 적용
스트리밍 중 DB 세션 관리가 불안정 수정
'''

import json
from datetime import datetime, timezone
import httpx
import tiktoken
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    OLLAMA_TAGS_URL,
    SYSTEM_PROMPT,
    MAX_HISTORY_MESSAGES,
    MAX_CONTEXT_TOKENS,
    RESERVED_TOKENS,
)
from app.database.database import get_db, SessionLocal
from app.database.models import ChatSession, ChatMessage
from app.ollama_client import ollama_stream
from app.schemas import ChatRequest

router = APIRouter()

def trim_history_by_tokens(messages: list[ChatMessage], max_tokens: int) -> list[ChatMessage]:
    """
    메시지 리스트를 토큰 수 기준으로 잘라냅니다.
    최신 메시지를 우선으로 유지하면서 max_tokens를 넘지 않도록 자릅니다.
    """
    if not messages:
        return []

    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        encoding = tiktoken.get_encoding("gpt2")

    total_tokens = 0
    trimmed = []

    for msg in reversed(messages):
        content = msg.content or ""
        token_count = len(encoding.encode(content))

        if total_tokens + token_count > max_tokens:
            break

        trimmed.append(msg)
        total_tokens += token_count

    return list(reversed(trimmed))

@router.get("/models")
async def list_models():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(OLLAMA_TAGS_URL)
            response.raise_for_status()
            data = response.json()
        return {"models": [m["name"] for m in data.get("models", [])]}
    except httpx.ConnectError:
        return {"models": [], "error": "Ollama 서버에 연결할 수 없습니다."}
    except Exception as e:
        return {"models": [], "error": str(e)}

@router.post("/chat")
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db, scope="function")):
    # 1. 세션 조회
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == payload.session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    model = payload.model or session.model
    if not model:
        raise HTTPException(status_code=400, detail="모델이 지정되지 않았습니다.")

    # 2. 사용자 메시지 저장
    if not payload.regenerate:
        if not payload.message:
            raise HTTPException(status_code=400, detail="message가 필요합니다.")

        db.add(ChatMessage(session_id=payload.session_id, role="user", content=payload.message))

        if session.title == "새 대화":
            session.title = payload.message[:20] + ("…" if len(payload.message) > 20 else "")

        await db.commit()

    # 3. 히스토리 조회 (메시지 수 제한)
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == payload.session_id)
        .order_by(ChatMessage.id.desc())
        .limit(MAX_HISTORY_MESSAGES)
    )
    history = list(history_result.scalars().all())
    history.reverse()

    # === 토큰 기반으로 추가 필터링 ===
    available_tokens = MAX_CONTEXT_TOKENS - RESERVED_TOKENS
    history = trim_history_by_tokens(history, available_tokens)

    ollama_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    ollama_messages += [{"role": m.role, "content": m.content} for m in history]

    # ============================================================
    # 스트리밍 중 DB 세션 사용하지 않음
    # ============================================================
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
            async with SessionLocal() as new_db:
                result = await new_db.execute(
                    select(ChatSession).where(ChatSession.id == payload.session_id)
                )
                new_session = result.scalar_one_or_none()

                if new_session:
                    new_db.add(ChatMessage(
                        session_id=payload.session_id,
                        role="assistant",
                        content=full_text
                    ))
                    new_session.updated_at = datetime.now(timezone.utc)
                    await new_db.commit()

    return StreamingResponse(
        stream_and_save(),
        media_type="application/x-ndjson; charset=utf-8",
    )