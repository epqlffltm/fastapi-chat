#app/main.py

'''
2026-07-09
챗봇 서버 해본 것
2026-07-09
챗봇 서버 - 대화 기록(멀티턴) 반영
'''

import httpx
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI()
templates = Jinja2Templates(directory="templates")

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"

SYSTEM_PROMPT = (
    "당신은 친절한 도우미입니다. 반드시 한국어(한글)로만 답변하세요. "
    "숫자, 로마자 알파벳(A-Z)은 필요한 경우에만 최소한으로 사용하세요. "
    "한자, 히라가나, 가타카나 등 한글이 아닌 다른 나라 문자는 절대 사용하지 마세요. "
    "목록을 나열할 때는 각 항목을 반드시 줄바꿈으로 구분하세요. "
    "문단이 바뀔 때도 줄바꿈을 사용해 가독성 있게 작성하세요."
)



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
    return templates.TemplateResponse(request, "index.html", {"title": "Chat"})


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
                "options": {"num_thread": 6},
            },
        )
        data = response.json()

    if "message" not in data:
        return {"error": data}

    return {"reply": data["message"]["content"]}