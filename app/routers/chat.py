# app/routers/chat.py

"""
2026-07-11
GET /models, POST /chat
챗봇 서버 - Pydantic 스키마 정의(app/schemas.py)로 이동
스키마 정의 제거, import로 교체

2026-07-14
Ollama가 꺼져있을 때 앱이 죽는 버그 수정
비동기 수정
비동기 SQLAlchemy 적용 + Ollama 연결 실패 처리
토큰 기반 히스토리 관리 적용
스트리밍 중 DB 세션 관리가 불안정 수정

2026-07-15
/models 가 실패를 200+error 로 반환하던 것을 503 으로 교체.
tiktoken 제거. 컨텍스트 예산을 Ollama에서 조회한 실제 값으로 계산.
히스토리를 대화 쌍 단위로 자르도록 수정.

2026-09-30
최신 메시지는 항상 포함. 그 하나만으로 예산을 넘으면 413 (저장·스트리밍 전에 거절).
에러로 끊긴 부분 응답은 저장하지 않는다 (done 까지 받은 경우만 저장).
"""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    CONTEXT_LIMIT,
    MAX_HISTORY_MESSAGES,
    RESERVE_FOR_REPLY,
    SYSTEM_PROMPT,
)
from app.database.database import SessionLocal, get_db
from app.database.models import ChatMessage, ChatSession
from app.ollama_client import (
    OllamaUnavailable,
    _raw_estimate,
    estimate_tokens,
    get_context_length,
    list_models,
    observe_actual,
    ollama_stream,
)
from app.schemas import ChatRequest

router = APIRouter()


class ContextBudgetExceeded(ValueError):
    """최신 메시지 하나만으로 컨텍스트 예산을 넘는다. 라우터가 413 으로 바꾼다."""


def trim_history(messages: list[ChatMessage], model: str, budget: int) -> list[ChatMessage]:
    """최신 메시지부터 예산까지 채우되, 대화 쌍이 깨지지 않게 한다.

    토큰 수만 보고 자르면 user 질문이 잘려나가고 assistant 답변만 남아
    히스토리가 assistant 로 시작하는 일이 생긴다. 모델 입장에서는
    "아무도 안 물어봤는데 내가 답한" 대화가 되므로 앞의 고아 답변은 떼어낸다.

    최신 메시지(지금 보낸 질문)는 반드시 포함한다. 이전엔 그것마저 예산을 넘으면
    빈 리스트가 되어 모델이 시스템 프롬프트만 받고 엉뚱한 답을 했다.
    그 하나로도 넘치면 조용히 자르지 않고 ContextBudgetExceeded 를 던진다.
    """
    kept: list[ChatMessage] = []
    used = 0

    for i, message in enumerate(reversed(messages)):
        cost = estimate_tokens(message.content or "", model)
        if used + cost > budget:
            if i == 0:
                raise ContextBudgetExceeded
            break
        kept.append(message)
        used += cost

    kept.reverse()

    while kept and kept[0].role == "assistant":
        kept.pop(0)

    return kept


@router.get("/models", status_code=200)
async def get_models():
    """실패는 상태 코드로 말한다.

    이전 버전은 200 + {"error": "..."} 를 반환했다. 두 가지가 틀렸다:
    1. 의존 서비스가 죽었는데 200이면 모니터링/헬스체크/curl -f 가 전부 성공으로 본다.
    2. str(httpx.ReadTimeout()) 은 빈 문자열이다. → {"error": ""} → 프론트의
        if (data.error) 가 falsy 판정 → 배너가 안 뜨고 빈 드롭다운으로 "정상" 진입.
        인밴드 에러 신호가 조용히 사라지는 경로가 실재했다.
    """
    try:
        return {"models": await list_models()}
    except OllamaUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/chat", status_code=200)
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db, scope="function")):
    # scope="function": 경로 함수가 끝나면 DB 세션이 반납된다 — 응답이 나가기 전에.
    # 스트리밍은 응답 단계이므로, LLM이 몇 분씩 생성하는 동안 커넥션을 물고 있지 않는다.
    result = await db.execute(select(ChatSession).where(ChatSession.id == payload.session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    model = payload.model or session.model
    if not model:
        raise HTTPException(status_code=400, detail="모델이 지정되지 않았습니다.")

    if not payload.regenerate and not payload.message:
        raise HTTPException(status_code=400, detail="message가 필요합니다.")

    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == payload.session_id)
        .order_by(ChatMessage.id.desc())
        .limit(MAX_HISTORY_MESSAGES)
    )
    history = list(history_result.scalars().all())
    history.reverse()

    # 새 질문은 예산 검사를 통과한 뒤에 저장한다. 413 으로 거절된 메시지가
    # DB 에 남으면 다음 요청마다 히스토리에 끼어 같은 문제를 반복한다.
    new_message = None
    if not payload.regenerate:
        new_message = ChatMessage(
            session_id=payload.session_id, role="user", content=payload.message
        )
        history = (history + [new_message])[-MAX_HISTORY_MESSAGES:]

    # --- 컨텍스트 예산 ---
    # 모델의 진짜 최대 컨텍스트를 /api/show 에서 읽고, VRAM 안전 상한과 min().
    # 이 값을 num_ctx 로 명시해서 보내므로, Ollama가 뭘 고를지 추측할 필요가 없다.
    model_context = await get_context_length(model)
    num_ctx = min(model_context, CONTEXT_LIMIT)

    # 시스템 프롬프트도 컨텍스트를 먹는다. 이전엔 RESERVED_TOKENS 안에 뭉뚱그려
    # 있다고 가정했는데, 프롬프트는 사용자가 txt로 넣는 가변 길이다.
    system_cost = estimate_tokens(SYSTEM_PROMPT, model)
    budget = num_ctx - RESERVE_FOR_REPLY - system_cost

    try:
        history = trim_history(history, model, max(budget, 0))
    except ContextBudgetExceeded as exc:
        # 스트리밍 시작 전이므로 아직 상태 코드를 바꿀 수 있다.
        raise HTTPException(
            status_code=413,
            detail="메시지가 너무 깁니다. 모델의 컨텍스트 한도를 넘어 보낼 수 없습니다.",
        ) from exc

    if new_message is not None:
        db.add(new_message)
        if session.title == "새 대화":
            session.title = payload.message[:20] + ("…" if len(payload.message) > 20 else "")
        await db.commit()

    ollama_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    ollama_messages += [{"role": m.role, "content": m.content} for m in history]

    session_id = payload.session_id  # 스트리밍 중엔 ORM 객체를 건드리지 않는다
    think = payload.think

    # 실제로 보낸 프롬프트 전체의 순수 근사값. done 청크의 prompt_eval_count(진짜 토큰 수)와
    # 짝지어 추정기를 보정한다. 다음 요청부터 이 모델의 자르기 판단이 더 정확해진다.
    prompt_text = "".join(m["content"] for m in ollama_messages)
    prompt_raw = _raw_estimate(prompt_text)

    async def stream_and_save():
        full_text = ""
        # stats 이벤트는 Ollama 의 done 청크에서만 나온다 = 생성이 끝까지 완료됐다.
        # 에러로 중간에 끊긴 답변을 완성본처럼 저장하면, 다음 요청의 히스토리에
        # 잘린 문장이 섞여 들어간다. 완료된 경우만 저장한다.
        completed = False

        async for chunk in ollama_stream(model, ollama_messages, think, num_ctx):
            try:
                evt = json.loads(chunk)
                if evt.get("type") == "content":
                    full_text += evt["text"]
                elif evt.get("type") == "stats":
                    completed = True
                    if evt.get("prompt_tokens"):
                        observe_actual(model, prompt_raw, evt["prompt_tokens"])
            except json.JSONDecodeError:
                pass
            yield chunk

        if not completed or not full_text:
            return

        # 쓸 때만 새 세션을 연다.
        async with SessionLocal() as write_db:
            result = await write_db.execute(select(ChatSession).where(ChatSession.id == session_id))
            target = result.scalar_one_or_none()
            if target is None:
                return  # 생성 중에 세션이 삭제됐다

            write_db.add(ChatMessage(session_id=session_id, role="assistant", content=full_text))
            target.updated_at = datetime.now(UTC)
            await write_db.commit()

    return StreamingResponse(
        stream_and_save(),
        media_type="application/x-ndjson; charset=utf-8",
    )
