#app/main.py

'''
2026-07-09
챗봇 서버 - 작성

2026-07-09
챗봇 서버 - 설정값 .env, 시스템 프롬프트 txt로 분리

2026-07-09
챗봇 서버 - 정적 파일(css/js) 분리

2026-07-09
챗봇 서버 - 스트리밍 응답 적용

2026-07-09
챗봇 서버 - thinking 모델 지원 (NDJSON 스트리밍)
'''

import json
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / "config" / ".env")

app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
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
    think: bool = False


async def get_default_model() -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(OLLAMA_TAGS_URL)
        data = response.json()
    models = data.get("models", [])
    if not models:
        raise RuntimeError("설치된 Ollama 모델이 없습니다.")
    return models[0]["name"]


def ndjson(event_type: str, text: str) -> str:
    return json.dumps({"type": event_type, "text": text}, ensure_ascii=False) + "\n"


async def ollama_stream(model: str, messages: list[dict], think: bool):
    """Ollama가 생성하는 thinking/content 토큰을 구분해서 NDJSON으로 흘려보냄"""
    timeout = httpx.Timeout(10.0, read=300.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                OLLAMA_URL,
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "think": think,
                    "options": {"num_thread": NUM_THREAD},
                },
            ) as response:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if data.get("error"):
                        yield ndjson("error", data["error"])
                        return

                    message = data.get("message", {})
                    thinking_piece = message.get("thinking")
                    content_piece = message.get("content")

                    if thinking_piece:
                        yield ndjson("thinking", thinking_piece)
                    if content_piece:
                        yield ndjson("content", content_piece)

                    if data.get("done"):
                        break

    except httpx.ReadTimeout:
        yield ndjson("error", "응답 생성이 너무 오래 걸려 시간 초과되었습니다.")
    except httpx.ConnectError:
        yield ndjson("error", "Ollama 서버에 연결할 수 없습니다. 서버가 켜져 있는지 확인해주세요.")


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

    return StreamingResponse(
        ollama_stream(model, ollama_messages, payload.think),
        media_type="application/x-ndjson; charset=utf-8",
    )