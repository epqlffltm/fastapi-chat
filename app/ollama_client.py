#app/ollama_client.py

'''
2026-07-11
Ollama API 통신 (스트리밍, 모델 조회)
'''

import json
import httpx
from app.config import OLLAMA_URL, OLLAMA_TAGS_URL, NUM_THREAD


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