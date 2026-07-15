# app/test/tast_api.py

"""이번 리뷰에서 찾은 버그들의 회귀 테스트.

각 테스트 이름 옆에 어떤 버그를 막는지 적어뒀다. 테스트가 없어서 이 버그들이
프로덕션까지 갔다는 게 이 파일의 존재 이유다.
"""

import ast
import inspect
import json
from pathlib import Path

import httpx
from conftest import OLLAMA, ndjson_events

from app import ollama_client
from app.routers import chat
from app.routers.chat import trim_history

# ══════════════════════════════════════════════════════════════
# /models — 실패는 상태 코드로 말해야 한다
# ══════════════════════════════════════════════════════════════


def test_models_ok(client, ollama):
    r = client.get("/models")
    assert r.status_code == 200
    assert r.json()["models"] == ["qwen3:8b"]


def test_models_returns_503_when_ollama_down(client, ollama):
    """[회귀] 이전엔 200 + {"error": "..."} 를 반환했다.

    의존 서비스가 죽었는데 200이면 모니터링·헬스체크·curl -f 가 전부 성공으로 본다.
    """
    ollama.get(f"{OLLAMA}/api/tags").mock(side_effect=httpx.ConnectError("refused"))

    r = client.get("/models")
    assert r.status_code == 503
    assert "ollama serve" in r.json()["detail"]


def test_models_503_on_timeout_with_nonempty_detail(client, ollama):
    """[회귀] str(httpx.ReadTimeout()) 은 빈 문자열이다.

    이전 코드: except Exception as e: return {"models": [], "error": str(e)}
    → {"error": ""} → 프론트의 if (data.error) 가 falsy 판정 → 배너가 안 뜸
    → 빈 드롭다운으로 '정상' 경로 진입 → startNewSession({model: ""}) → /chat 400.

    인밴드 에러 신호가 조용히 사라지는 경로가 실재했다.
    """
    assert str(httpx.ReadTimeout("")) == ""  # 전제 자체를 검증

    ollama.get(f"{OLLAMA}/api/tags").mock(side_effect=httpx.ReadTimeout(""))

    r = client.get("/models")
    assert r.status_code == 503
    assert r.json()["detail"].strip()  # 빈 문자열이면 실패


# ══════════════════════════════════════════════════════════════
# 토큰 추정기 — tiktoken 없이, prompt_eval_count 로 자가보정
# ══════════════════════════════════════════════════════════════


def test_no_tiktoken_anywhere():
    """[회귀] tiktoken 은 런타임에 openaipublic.blob.core.windows.net 에서
    인코딩 파일을 다운로드한다. 로컬 추론 앱이 OpenAI 서버에 의존하면 안 된다.
    (게다가 except 폴백의 gpt2 도 같은 호스트를 타서 폴백 역할을 못 했다.)
    """

    app_dir = Path(__file__).resolve().parent.parent / "app"
    offenders = []

    # 주석에 'tiktoken' 이라고 써 있는 건 상관없다. import 를 잡아야 한다.
    # (문자열 검색으로 짰다가 이 파일의 주석에 스스로 걸렸다.)
    for path in app_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(a.name.split(".")[0] == "tiktoken" for a in node.names):
                    offenders.append(path.name)
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] == "tiktoken":
                    offenders.append(path.name)

    assert offenders == []


def test_estimator_calibrates_from_prompt_eval_count(client, session, ollama):
    """추정기가 Ollama의 실측값으로 보정된다."""
    before = ollama_client.current_ratio("qwen3:8b")
    assert before == 1.0  # 아직 아무것도 안 봤으니 초기값

    client.post("/chat", json={"session_id": session, "message": "안녕하세요"})

    after = ollama_client.current_ratio("qwen3:8b")
    assert after != before  # prompt_eval_count=137 을 보고 학습했다
    assert 0 < after < 10


def test_trim_history_never_starts_with_assistant():
    """[회귀] 토큰 수만 보고 자르면 user 질문이 잘려나가고 assistant 답변만 남는다.

    모델 입장에선 '아무도 안 물어봤는데 내가 답한' 대화가 된다.
    """

    class Msg:
        def __init__(self, role, content):
            self.role, self.content = role, content

    history = [
        Msg("user", "가" * 500),
        Msg("assistant", "나" * 500),
        Msg("user", "다" * 10),
        Msg("assistant", "라" * 10),
    ]

    # 앞의 긴 쌍은 못 들어갈 만큼 작은 예산 → 뒤의 짧은 쌍만 남아야 한다
    kept = trim_history(history, "qwen3:8b", budget=60)

    assert kept, "예산 안에 들어가는 메시지가 있는데 전부 잘렸다"
    assert kept[0].role == "user", "히스토리가 고아 assistant 답변으로 시작한다"


def test_system_prompt_counted_in_budget():
    """[회귀] RESERVED_TOKENS 가 '응답 + 시스템 프롬프트' 몫이라고 해놓고
    정작 SYSTEM_PROMPT 토큰은 아무 데서도 세지 않았다.
    시스템 프롬프트는 사용자가 txt 로 넣는 가변 길이다.
    """

    source = inspect.getsource(chat.chat)
    assert "estimate_tokens(SYSTEM_PROMPT" in source


# ══════════════════════════════════════════════════════════════
# /chat — 스트리밍, 저장, 메트릭
# ══════════════════════════════════════════════════════════════


def test_chat_streams_and_saves(client, session, ollama):
    r = client.post("/chat", json={"session_id": session, "message": "안녕하세요"})
    assert r.status_code == 200

    events = ndjson_events(r)
    content = "".join(e["text"] for e in events if e["type"] == "content")
    assert content == "안녕하세요"

    # 스트리밍이 끝난 뒤 새 SessionLocal() 로 저장된다
    messages = client.get(f"/sessions/{session}/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "안녕하세요"


def test_chat_emits_stats_event(client, session, ollama):
    """[신규] done 청크의 지표를 버리지 않고 stats 이벤트로 내보낸다."""
    r = client.post("/chat", json={"session_id": session, "message": "안녕"})

    stats = [e for e in ndjson_events(r) if e["type"] == "stats"]
    assert len(stats) == 1

    s = stats[0]
    assert s["prompt_tokens"] == 137  # 모델의 진짜 토크나이저가 센 값
    assert s["output_tokens"] == 5
    assert s["tokens_per_sec"] == 20.0  # eval_count 5 / eval_duration 0.25s
    assert s["ttft_ms"] is not None


def test_chat_sends_explicit_num_ctx(client, session, ollama):
    """[회귀] num_ctx 를 안 보내면 Ollama가 VRAM 보고 알아서 정한다.

    그러면 히스토리를 몇 토큰까지 채워도 되는지 우리가 알 수 없다.
    이전엔 8192 를 코드에 박아뒀는데 실제 창은 32768 이었다 (창의 25%만 사용).
    """
    client.post("/chat", json={"session_id": session, "message": "안녕"})

    sent = ollama.calls.last.request

    body = json.loads(sent.content)
    # /api/show 가 40960 을 주고, CONTEXT_LIMIT 이 32768 → min = 32768
    assert body["options"]["num_ctx"] == 32768


def test_chat_404_on_missing_session(client, ollama):
    r = client.post("/chat", json={"session_id": "nope", "message": "안녕"})
    assert r.status_code == 404


def test_chat_400_without_message(client, session, ollama):
    r = client.post("/chat", json={"session_id": session})
    assert r.status_code == 400


def test_context_length_falls_back_when_show_fails(client, session, ollama):
    """/api/show 가 죽어도 채팅은 되어야 한다. 컨텍스트를 못 알아내는 건
    채팅을 막을 이유가 아니다."""
    ollama.post(f"{OLLAMA}/api/show").mock(side_effect=httpx.ConnectError("x"))

    r = client.post("/chat", json={"session_id": session, "message": "안녕"})
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════
# 세션 / 검색
# ══════════════════════════════════════════════════════════════


def test_search_by_title_and_content(client, ollama):
    a = client.post("/sessions", json={"model": "qwen3:8b"}).json()["id"]
    b = client.post("/sessions", json={"model": "qwen3:8b"}).json()["id"]
    client.patch(f"/sessions/{a}", json={"title": "도커 질문"})
    client.patch(f"/sessions/{b}", json={"title": "파이썬 질문"})

    hits = client.get("/sessions/search", params={"q": "도커"}).json()
    assert [s["id"] for s in hits] == [a]

    assert client.get("/sessions/search", params={"q": "없는말"}).json() == []


def test_delete_messages_from(client, session, ollama):
    client.post("/chat", json={"session_id": session, "message": "첫번째"})
    client.post("/chat", json={"session_id": session, "message": "두번째"})

    messages = client.get(f"/sessions/{session}/messages").json()
    assert len(messages) == 4

    # 세 번째 메시지부터 삭제 (= 두번째 질문을 수정하는 상황)
    client.delete(f"/sessions/{session}/messages/from/{messages[2]['id']}")

    remaining = client.get(f"/sessions/{session}/messages").json()
    assert len(remaining) == 2
