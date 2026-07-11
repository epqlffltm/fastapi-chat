# app/schemas.py

'''
2026-07-11
챗봇 서버 - Pydantic 스키마 정의
'''

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    think: bool = False