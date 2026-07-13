#app/routers/sessions.py

'''
2026-07-13
스키마 정의 제거, import로 교체
'''

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.database.models import ChatSession, ChatMessage
from app.schemas import SessionCreate, SessionUpdate, SessionOut, MessageOut

router = APIRouter()

@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db)):
    return db.query(ChatSession).order_by(ChatSession.updated_at.desc()).all()

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
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete(synchronize_session=False)
    session.title = "새 대화"
    db.commit()
    return {"cleared": True}

@router.delete("/sessions/{session_id}/messages/from/{message_id}")
def delete_messages_from(session_id: str, message_id: int, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id,
        ChatMessage.id >= message_id,
    ).delete(synchronize_session=False)
    db.commit()
    return {"deleted": True}