# app/ollama_client.py

"""
2026-07-11
Ollama API 통신 (스트리밍, 모델 조회)

2026-07-15
tiktoken 제거 → Ollama가 done 청크로 주는 실제 토큰 수 사용 + stats 이벤트 방출
연결 실패를 OllamaUnavailable 예외로 명시화 (라우터가 503으로 변환)
/api/show 로 모델의 실제 컨텍스트 길이 조회
"""

import json
import time

import httpx

from app.config import (
    CONTEXT_FALLBACK,
    NUM_THREAD,
    OLLAMA_SHOW_URL,
    OLLAMA_TAGS_URL,
    OLLAMA_URL,
)


class OllamaUnavailable(RuntimeError):
    """Ollama에 닿지 못했거나, 닿았지만 쓸 수 없는 상태.

    라우터가 이걸 잡아 503 + detail 로 바꾸고, detail 은 그대로 프론트 배너에 뜬다.
    httpx.ReadTimeout 등은 str()이 빈 문자열이라, 여기서 항상 사람이 읽을 메시지를 채운다.
    """


async def list_models() -> list[str]:
    """설치된 모델 이름 목록. 실패 시 OllamaUnavailable."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(OLLAMA_TAGS_URL)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        raise OllamaUnavailable(
            "Ollama 서버가 응답하지 않습니다. 모델을 불러오는 중이거나 서버가 멈췄을 수 있습니다."
        ) from exc
    except httpx.ConnectError as exc:
        raise OllamaUnavailable(
            "Ollama 서버에 연결할 수 없습니다. 터미널에서 ollama serve 가 실행 중인지 확인하세요."
        ) from exc
    except httpx.HTTPError as exc:
        raise OllamaUnavailable(f"Ollama 서버가 정상 응답하지 않습니다: {exc}") from exc

    return [m["name"] for m in data.get("models", [])]


# 모델별 컨텍스트 길이를 한 번 읽으면 캐싱한다. /api/show 는 매 요청 부를 필요가 없다.
_context_cache: dict[str, int] = {}


async def get_context_length(model: str) -> int:
    """모델의 최대 컨텍스트 길이(토큰)를 /api/show 에서 읽는다.

    응답의 model_info 안에 '<arch>.context_length' 형태로 들어있다(arch는 모델마다 다름).
    실패하거나 못 찾으면 보수적 폴백. 이 조회 실패로 채팅 전체가 죽지는 않게 한다.
    """
    if model in _context_cache:
        return _context_cache[model]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(OLLAMA_SHOW_URL, json={"model": model})
            response.raise_for_status()
            info = response.json().get("model_info", {})
    except httpx.HTTPError:
        return CONTEXT_FALLBACK

    ctx = next(
        (v for k, v in info.items() if k.endswith(".context_length") and isinstance(v, int)),
        CONTEXT_FALLBACK,
    )
    _context_cache[model] = ctx
    return ctx


def _raw_estimate(text: str) -> int:
    """문자 클래스 기반 순수 근사 (보정 전).

    CJK 문자는 대략 토큰당 1자, 영문/공백은 토큰당 약 4자. 이 비율은 모델 토크나이저마다
    다르므로, 아래 보정 계수로 실측에 맞춰 나간다.
    """
    if not text:
        return 0
    cjk = sum(
        1
        for ch in text
        if "\u3000" <= ch <= "\u9fff" or "\uac00" <= ch <= "\ud7a3" or "\uf900" <= ch <= "\ufaff"
    )
    other = len(text) - cjk
    return cjk + (other // 4) + 1


# 모델별 보정 계수. 실제 토큰 수 / 순수 근사값. 1.0 에서 시작해 실측으로 수렴한다.
_ratio: dict[str, float] = {}
_RATIO_ALPHA = 0.3  # EMA 가중치. 클수록 최신 관측에 빠르게 반응.


def current_ratio(model: str) -> float:
    """이 모델의 현재 보정 계수. 아직 아무것도 관측 안 했으면 1.0."""
    return _ratio.get(model, 1.0)


def observe_actual(model: str, raw_estimate: int, actual_tokens: int) -> None:
    """Ollama가 준 실제 토큰 수(prompt_eval_count)로 보정 계수를 갱신한다.

    tiktoken 없이도 시간이 지나면 이 모델의 진짜 토크나이저 비율로 수렴한다 —
    외부 의존성 없이 로컬에서 자기교정. EMA 라 한 번의 이상치에 휘둘리지 않는다.
    """
    if raw_estimate <= 0 or actual_tokens <= 0:
        return
    observed = actual_tokens / raw_estimate
    prev = _ratio.get(model, 1.0)
    _ratio[model] = (1 - _RATIO_ALPHA) * prev + _RATIO_ALPHA * observed


def estimate_tokens(text: str, model: str) -> int:
    """히스토리를 자르기 위한 토큰 수 추정 (보정 계수 적용).

    정확한 값은 Ollama가 done 청크로 주지만 그건 보낸 뒤에야 안다. 자를지는 보내기 전에
    정해야 하므로 여기서 추정한다. tiktoken 을 쓰지 않는다 — 그건 런타임에 OpenAI 서버에서
    인코딩을 받아오고(로컬 앱에 외부 의존성), cl100k 는 Qwen 토크나이저와도 다르다.
    """
    raw = _raw_estimate(text)
    return int(raw * current_ratio(model)) if raw else 0


def ndjson(event_type: str, **fields) -> str:
    """한 줄 = JSON 객체 하나. text 이벤트뿐 아니라 stats(토큰/속도)도 실어 나른다."""
    return json.dumps({"type": event_type, **fields}, ensure_ascii=False) + "\n"


def _compute_stats(data: dict, ttft_seconds: float | None) -> dict:
    """done 청크의 원시 카운터를 UI가 바로 쓸 값으로 환산.

    Ollama 시간 단위는 나노초. prompt_eval_count 는 Qwen 자신의 토크나이저가 센
    값이라 어떤 외부 추정보다 정확하다. tok/s = eval_count / eval_duration.
    """
    prompt_tokens = data.get("prompt_eval_count")
    eval_tokens = data.get("eval_count")
    eval_ns = data.get("eval_duration")

    tokens_per_sec = None
    if eval_tokens and eval_ns:
        tokens_per_sec = round(eval_tokens / (eval_ns / 1e9), 1)

    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": eval_tokens,
        "tokens_per_sec": tokens_per_sec,
        "ttft_ms": round(ttft_seconds * 1000) if ttft_seconds is not None else None,
    }


async def ollama_stream(model: str, messages: list[dict], think: bool, num_ctx: int):
    """thinking/content 토큰을 구분해 NDJSON으로 중계하고, 끝에 stats 이벤트를 흘린다.

    num_ctx 를 명시적으로 보낸다 — Ollama가 기본값으로 뭘 고를지 추측하지 않는다.
    (이전엔 done 청크를 만나면 그냥 break 해서 토큰/속도 수치를 전부 버렸다.)
    """
    timeout = httpx.Timeout(10.0, read=300.0)
    start = time.perf_counter()
    ttft_seconds = None

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
                    "options": {"num_thread": NUM_THREAD, "num_ctx": num_ctx},
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
                        yield ndjson("error", text=data["error"])
                        return

                    message = data.get("message", {})
                    thinking_piece = message.get("thinking")
                    content_piece = message.get("content")

                    if thinking_piece:
                        yield ndjson("thinking", text=thinking_piece)
                    if content_piece:
                        if ttft_seconds is None:  # 첫 실제 토큰 = TTFT
                            ttft_seconds = time.perf_counter() - start
                        yield ndjson("content", text=content_piece)

                    if data.get("done"):
                        yield ndjson("stats", **_compute_stats(data, ttft_seconds))
                        break

    except httpx.ReadTimeout:
        yield ndjson("error", text="응답 생성이 너무 오래 걸려 시간 초과되었습니다.")
    except httpx.ConnectError:
        yield ndjson(
            "error",
            text="Ollama 서버에 연결할 수 없습니다. 서버가 켜져 있는지 확인해주세요.",
        )
