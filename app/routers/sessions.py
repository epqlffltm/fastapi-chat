#app/routers/sessions.py

'''
2026-07-13
스키마 정의 제거, import로 교체

2026-07-14
비동기 마이그레이션
'''

# app/routers/sessions.py

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.database import get_db
from app.database.models import ChatSession, ChatMessage
from app.schemas import SessionCreate, SessionUpdate, SessionOut, MessageOut

router = APIRouter()


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatSession).order_by(ChatSession.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/sessions/search", response_model=list[SessionOut])
async def search_sessions(q: str, db: AsyncSession = Depends(get_db)):
    query = q.strip()
    if not query:
        result = await db.execute(
            select(ChatSession).order_by(ChatSession.updated_at.desc())
        )
        return result.scalars().all()

    pattern = f"%{query}%"

    # 메시지 내용 검색
    msg_stmt = select(ChatMessage.session_id).where(
        ChatMessage.content.ilike(pattern)
    ).distinct()
    msg_result = await db.execute(msg_stmt)
    matching_ids = msg_result.scalars().all()

    stmt = (
        select(ChatSession)
        .where(
            (ChatSession.title.ilike(pattern)) | 
            (ChatSession.id.in_(matching_ids))
        )
        .order_by(ChatSession.updated_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/sessions", response_model=SessionOut)
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_db)):
    session = ChatSession(
        id=str(uuid.uuid4()),
        title="새 대화",
        model=payload.model
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def get_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id)
    )
    return result.scalars().all()


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def update_session(
    session_id: str, 
    payload: SessionUpdate, 
    db: AsyncSession = Depends(get_db)
):
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    if payload.title is not None:
        session.title = payload.title
    if payload.model is not None:
        session.model = payload.model

    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    
    await db.delete(session)
    await db.commit()
    return {"deleted": True}


@router.delete("/sessions/{session_id}/messages")
async def clear_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    await db.execute(
        delete(ChatMessage).where(ChatMessage.session_id == session_id)
    )
    session.title = "새 대화"
    await db.commit()
    return {"cleared": True}


@router.delete("/sessions/{session_id}/messages/from/{message_id}")
async def delete_messages_from(
    session_id: str, 
    message_id: int, 
    db: AsyncSession = Depends(get_db)
):
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    await db.execute(
        delete(ChatMessage).where(
            ChatMessage.session_id == session_id,
            ChatMessage.id >= message_id
        )
    )
    await db.commit()
    return {"deleted": True}