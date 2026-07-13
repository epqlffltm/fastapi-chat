#app/schemas/session.py

'''
2026-07-13
스키마 분리
'''

from datetime import datetime
from pydantic import BaseModel

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