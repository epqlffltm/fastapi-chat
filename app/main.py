#app/main.py

'''
2026-07-09
챗봇 서버 - 설정값 .env, 시스템 프롬프트 txt로 분리
'''

import os
from pathlib import Path
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent  # 프로젝트 루트

load_dotenv(BASE_DIR / "config" / ".env")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_URL = f"{OLLAMA_HOST}/api/chat"
OLLAMA_TAGS_URL = f"{OLLAMA_HOST}/api/tags"

NUM_THREAD = int(os.getenv("NUM_THREAD", "8"))
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "14"))

with open(BASE_DIR / "prompts" / "system_prompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read().strip()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]


async def get_default_model() -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(OLLAMA_TAGS_URL)
        data = response.json()
    models = data.get("models", [])
    if not models:
        raise RuntimeError("설치된 Ollama 모델이 없습니다.")
    return models[0]["name"]


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"title": "Chat", "max_history": MAX_HISTORY}
    )


@app.get("/models")
async def list_models():
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(OLLAMA_TAGS_URL)
        data = response.json()
    return {"models": [m["name"] for m in data.get("models", [])]}


@app.post("/chat")
async def chat(payload: ChatRequest):
    model = payload.model or await get_default_model()

    ollama_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    ollama_messages += [{"role": m.role, "content": m.content} for m in payload.messages]

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            OLLAMA_URL,
            json={
                "model": model,
                "messages": ollama_messages,
                "stream": False,
                "options": {"num_thread": NUM_THREAD},
            },
        )
        data = response.json()

    if "message" not in data:
        return {"error": data}

    return {"reply": data["message"]["content"]}