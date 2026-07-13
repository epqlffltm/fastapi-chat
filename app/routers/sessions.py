#app/routers/sessions.py

'''
2026-07-13

'''

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.database.models import ChatSession, ChatMessage

router = APIRouter()

class SessionCreate(BaseModel):
    model: str

class SessionUpdate(BaseModel):
    title: str | None = None
    model: str | None = None

class SessionOut(BaseModel):
    id: str
    title: str
    model: str
    updated_at: datetime

    class Config:
        from_attributes = True

class MessageOut(BaseModel):
    id: int
    role: str
    content: str

    class Config:
        from_attributes = True

@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db)):
    return db.query(ChatSession).order_by(ChatSession.updated_at.desc()).all()

@router.post("/sessions", response_model=SessionOut)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    session = ChatSession(id=str(uuid.uuid4()), title="새 대화", model=payload.model)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def get_messages(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    return session.messages

@router.patch("/sessions/{session_id}", response_model=SessionOut)
def update_session(session_id: str, payload: SessionUpdate, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    if payload.title is not None:
        session.title = payload.title
    if payload.model is not None:
        session.model = payload.model

    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session

@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    db.delete(session)
    db.commit()
    return {"deleted": True}

@router.delete("/sessions/{session_id}/messages")
def clear_messages(session_id: str, db: Session = Depends(get_db)):
    """이 세션의 메시지만 전부 지우고, 세션 자체(제목/모델)는 유지"""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete(synchronize_session=False)
    session.title = "새 대화"
    db.commit()
    return {"cleared": True}

@router.delete("/sessions/{session_id}/messages/from/{message_id}")
def delete_messages_from(session_id: str, message_id: int, db: Session = Depends(get_db)):
    """이 메시지(id)부터 그 이후 전부 삭제 — 수정/재시도의 기반 동작"""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id,
        ChatMessage.id >= message_id,
    ).delete(synchronize_session=False)
    db.commit()
    return {"deleted": True}

@router.get("/sessions/search", response_model=list[SessionOut])
def search_sessions(q: str, db: Session = Depends(get_db)):
    query = q.strip()
    if not query:
        return db.query(ChatSession).order_by(ChatSession.updated_at.desc()).all()

    pattern = f"%{query}%"

    matching_session_ids = (
        db.query(ChatMessage.session_id)
        .filter(ChatMessage.content.ilike(pattern))
        .distinct()
    )

    results = (
        db.query(ChatSession)
        .filter(
            ChatSession.title.ilike(pattern) | ChatSession.id.in_(matching_session_ids)
        )
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return results