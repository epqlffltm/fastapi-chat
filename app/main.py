#app/main.py

'''
2026-07-09
챗봇 서버 해본 것
'''

import httpx
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"

SYSTEM_PROMPT = (
    "당신은 친절한 도우미입니다. 사용자가 어떤 언어로 질문하든 항상 한국어로만 답변하세요. "
    "숫자나 코드는 그대로 써도 되지만, 설명은 반드시 한글로만 작성하세요. "
    "한자(중국어 문자)는 절대 사용하지 마세요."
)


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
async def chat(message: str = Form(...), model: str = Form(default=None)):
    if not model:
        model = await get_default_model()

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            OLLAMA_URL,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": message},
                ],
                "stream": False,
                "options": {"num_thread": 6},
            },
        )
        data = response.json()

    if "message" not in data:
        return {"error": data}

    return {"reply": data["message"]["content"]}