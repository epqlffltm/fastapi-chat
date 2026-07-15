# app/test/conftest.py

"""테스트 픽스처.

Ollama는 respx로 가짜를 세운다 — 테스트가 GPU나 네트워크에 의존하면 CI에서 못 돌린다.
DB는 테스트마다 tmp_path에 새로 만든다.
"""

import os
import tempfile
from pathlib import Path

import pytest

# app.config 가 import 시점에 DATABASE_URL 을 읽으므로, 그 전에 갈아끼운다.
_TMP_DB = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.as_posix()}"

import httpx  # noqa: E402
import respx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import ollama_client  # noqa: E402
from app.main import app  # noqa: E402

OLLAMA = "http://localhost:11434"


@pytest.fixture(autouse=True)
def _reset_client_caches():
    """모듈 전역 캐시(추정 비율, 컨텍스트 길이)를 테스트마다 초기화."""
    ollama_client._context_cache.clear()  # /api/show 결과 (모델→컨텍스트 길이)
    ollama_client._ratio.clear()  # 추정기 보정 계수
    yield


@pytest.fixture
def client():
    # 컨텍스트 매니저로 써야 lifespan(init_db)이 돈다.
    # 이걸 빼먹으면 "no such table: chat_sessions" 로 죽는다 —
    # @app.on_event 를 lifespan 으로 옮긴 이유 중 하나.
    with TestClient(app) as c:
        yield c


@pytest.fixture
def ollama():
    """가짜 Ollama. 기본은 '정상 동작'. 테스트가 필요하면 route를 덮어쓴다."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{OLLAMA}/api/tags").mock(
            return_value=httpx.Response(200, json={"models": [{"name": "qwen3:8b"}]})
        )
        mock.post(f"{OLLAMA}/api/show").mock(
            return_value=httpx.Response(200, json={"model_info": {"qwen3.context_length": 40960}})
        )
        mock.post(f"{OLLAMA}/api/chat").mock(
            return_value=httpx.Response(200, content=chat_stream())
        )
        yield mock


def chat_stream(
    content: str = "안녕하세요",
    prompt_eval_count: int = 137,
    eval_count: int = 5,
    eval_duration: int = 250_000_000,  # 0.25초 → 20 tok/s
) -> bytes:
    """Ollama의 NDJSON 스트림을 흉내낸다. 마지막 청크에 지표가 들어간다."""
    import json

    lines = [json.dumps({"message": {"content": ch}}) for ch in content]
    lines.append(
        json.dumps(
            {
                "done": True,
                "message": {"content": ""},
                "prompt_eval_count": prompt_eval_count,
                "prompt_eval_duration": 210_000_000,
                "eval_count": eval_count,
                "eval_duration": eval_duration,
                "total_duration": 500_000_000,
            }
        )
    )
    return ("\n".join(lines) + "\n").encode()


@pytest.fixture
def session(client, ollama):
    """qwen3:8b 로 세션 하나 만들어서 id 반환."""
    return client.post("/sessions", json={"model": "qwen3:8b"}).json()["id"]


def ndjson_events(response) -> list[dict]:
    import json

    return [json.loads(line) for line in response.text.strip().split("\n") if line.strip()]
