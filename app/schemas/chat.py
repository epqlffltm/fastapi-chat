# app/schemas/chat.py

"""
2026-07-13
스키마 분리
"""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str | None = None
    model: str | None = None
    think: bool = False
    regenerate: bool = False
