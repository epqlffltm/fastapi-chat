# fastapi-chat

FastAPI와 [Ollama](https://ollama.com)를 이용해 로컬 LLM을 서빙하는 채팅 애플리케이션입니다. GPU/CPU 환경에서 여러 모델을 자유롭게 전환하며 대화할 수 있고, 대화 기록은 SQLite에 저장되어 세션 단위로 관리됩니다.

<!-- TODO: 데모 GIF — ScreenToGif로 "질문 입력 → thinking 접힘 → 토큰 스트리밍 → 표 렌더링" 흐름을 10초 내외로 녹화해 docs/demo.gif로 저장 후 아래 주석 해제
![demo](docs/demo.gif)
-->

## 주요 기능

- **멀티 모델 지원**: 로컬에 설치된 Ollama 모델을 드롭다운에서 실시간으로 전환
- **스트리밍 응답**: NDJSON 프로토콜로 토큰 단위 실시간 출력 (타이핑 애니메이션)
- **추론 메트릭**: 응답마다 TTFT(첫 토큰까지 시간)와 tok/s를 말풍선 아래 표시
- **Thinking 모드**: Qwen3 등 추론 과정을 노출하는 모델의 사고 과정을 접이식 UI로 분리 표시
- **세션 기반 대화 관리**: SQLite에 대화 기록 저장, 사이드바에서 세션 목록 확인/전환/삭제
- **대화 검색**: 세션 제목과 메시지 본문을 함께 검색
- **메시지 수정·재시도**: DB의 메시지 ID 기준으로 특정 지점부터 대화를 다시 생성
- **코드 블록·표 렌더링**: 복사 버튼이 달린 코드 블록과 마크다운 표를 자동 렌더링
- **모델 별명**: 모델 태그 대신 원하는 이름으로 표시 (브라우저 로컬 저장)

## 기술 스택

| 영역 | 기술 |
|---|---|
| 백엔드 | FastAPI, httpx (Ollama와 비동기 스트리밍 통신) |
| DB | SQLite + SQLAlchemy (async) |
| 패키지 관리 | [uv](https://docs.astral.sh/uv/) |
| 프론트엔드 | Vanilla JS / HTML / CSS (프레임워크 없음) |
| LLM 서빙 | Ollama (로컬, GPU) |
| 배포 | Docker (앱 컨테이너 + 호스트 Ollama) |
| 테스트 | pytest + respx (Ollama 목킹), GitHub Actions CI |

## 아키텍처

```
app/
├── main.py                  # FastAPI 앱 조립, 라우터 연결, lifespan
├── config.py                # .env·시스템 프롬프트 로딩, DB 경로, 토큰 예산 상수
├── ollama_client.py         # Ollama API 스트리밍 통신, 토큰 추정, 컨텍스트 길이 조회
├── database/
│   ├── database.py          # SQLAlchemy 비동기 엔진/세션, 테이블 자동 생성
│   └── models.py            # ChatSession, ChatMessage 테이블 정의
├── schemas/
│   ├── chat.py              # 채팅 요청 스키마
│   └── session.py           # 세션/메시지 요청·응답 스키마
├── routers/
│   ├── pages.py             # 화면 렌더링 (GET /)
│   ├── chat.py              # 채팅 API (GET /models, POST /chat)
│   └── sessions.py          # 세션 CRUD·검색 API
└── test/
    ├── conftest.py          # 테스트 픽스처 (Ollama 목킹)
    └── test_api.py          # 회귀 테스트

templates/
└── index.html               # 메인 화면 (Jinja2)

static/
├── css/style.css            # 전체 스타일 (다크 테마)
└── js/
    ├── session-store.js     # 세션 목록/전환/검색 상태 관리
    ├── message-render.js    # 메시지·코드블록·표 렌더링, 스크롤 고정
    ├── chat-actions.js      # 스트리밍 요청, 수정/재시도
    └── app.js               # 진입점, 이벤트 바인딩

prompts/
├── system_prompt.txt            # 개인 시스템 프롬프트 (git 미포함, 선택)
└── system_prompt.example.txt    # 기본 시스템 프롬프트 (폴백용)

data/
└── chat.db                  # SQLite DB (git 미포함, 첫 실행 시 자동 생성)

Dockerfile                   # 멀티스테이지 빌드 (uv → slim 런타임)
compose.yaml                 # 앱 컨테이너 + 호스트 Ollama 연결
pull_models.py               # Ollama 모델 일괄 다운로드 스크립트
```

### 요청 흐름

```
브라우저 (JS)
   │  POST /chat  { session_id, message, model, think }
   ▼
FastAPI (routers/chat.py)
   │  1. 사용자 메시지를 DB에 저장
   │  2. 토큰 예산 내에서 최근 대화 기록 조회
   │     (/api/show로 모델 컨텍스트 길이 확인, 시스템 프롬프트 몫 차감)
   │  3. Ollama에 스트리밍 요청 (num_ctx 명시)
   ▼
Ollama (/api/chat, stream=True)
   │  토큰 단위로 thinking / content 청크 전송, 마지막에 done(토큰 카운터)
   ▼
FastAPI가 NDJSON으로 중계하며 응답 전문을 누적
   │  {"type": "thinking" | "content" | "error"}
   │  {"type": "stats", "prompt_tokens", "output_tokens", "tokens_per_sec", "ttft_ms"}
   ▼
브라우저가 실시간 렌더링
   (스트림 완료 시점에 FastAPI가 누적된 응답을 새 DB 세션으로 저장하고,
    브라우저는 DB 기준으로 메시지 목록을 재동기화)
```

## 시작하기

### 요구 사항

- [Ollama](https://ollama.com/download) — 로컬에 설치되어 실행 중이어야 함
- Docker 실행 시: Docker Desktop
- 로컬 개발 시: Python 3.13 + [uv](https://docs.astral.sh/uv/getting-started/installation/)

### 모델 다운로드

Ollama 서버가 실행 중인 상태에서:

```powershell
ollama pull qwen3:8b
```

여러 모델을 한 번에 받으려면 `pull_models.py`의 `MODELS` 리스트를 수정해 사용하세요.

```powershell
uv run python pull_models.py
```

### 실행

**Docker (권장)**

Ollama가 호스트에서 실행 중인 상태에서:

```powershell
docker compose up --build
```

앱만 컨테이너에서 돌고, `host.docker.internal`을 통해 호스트의 Ollama(GPU)에 연결됩니다. 대화 기록(`data/chat.db`)은 호스트 볼륨에 저장되어 컨테이너를 지워도 유지됩니다.

**로컬 개발**

```powershell
git clone https://github.com/epqlffltm/fastapi-chat.git
cd fastapi-chat
uv sync
uv run uvicorn app.main:app --reload
```

둘 다 브라우저에서 `http://localhost:8000` 으로 접속합니다.

### 환경 설정 (선택)

별도 설정 없이 바로 실행됩니다. 환경변수는 기본값이 적용되고, 시스템 프롬프트는 `prompts/system_prompt.example.txt`가 자동으로 사용되며, DB는 첫 실행 시 자동 생성됩니다. 커스터마이징하려면 예시 파일을 복사해서 수정하세요.

```powershell
Copy-Item prompts\system_prompt.example.txt prompts\system_prompt.txt
```

## 환경변수

모두 기본값이 있어 설정 없이도 동작합니다.

| 변수 | 설명 | 기본값 |
|---|---|---|
| `OLLAMA_HOST` | Ollama 서버 주소 (Docker에서는 `host.docker.internal`) | `http://localhost:11434` |
| `NUM_THREAD` | CPU 추론 시 사용할 스레드 수 (물리 코어 수 기준 권장) | `8` |
| `CONTEXT_LIMIT` | 컨텍스트 창 상한 (모델 실제값과 min, VRAM 안전장치) | `32768` |
| `CONTEXT_FALLBACK` | `/api/show` 조회 실패 시 컨텍스트 폴백값 | `8192` |
| `RESERVE_FOR_REPLY` | 생성될 응답을 위해 예산에서 떼어둘 토큰 | `2048` |
| `MAX_HISTORY_MESSAGES` | 히스토리로 보낼 최대 메시지 개수 (토큰 예산과 별개인 안전장치) | `40` |
| `DATABASE_URL` | DB 연결 문자열 (미설정 시 `data/chat.db` 자동 사용) | - |

> 히스토리 길이는 개수와 토큰 예산 **둘 다**로 제한됩니다. 실제 컨텍스트 창 크기는 모델마다 다르므로 `/api/show`로 조회하며, 시스템 프롬프트 토큰은 예산에서 별도로 차감합니다. 자세한 근거는 [DECISIONS.md](DECISIONS.md) 참고.

## 설계 결정과 의도적 한계

주요 기술 선택의 **근거**(tiktoken 대신 자기보정 추정기를 쓴 이유, 스트리밍 중 DB 커넥션 수명, 실패를 상태 코드로 표현하는 이유, Docker에서 Ollama를 호스트에 둔 이유 등)와, 이 프로젝트가 **범위에 맞춰 일부러 하지 않은 것**(인증, 다중 사용자, 마이그레이션 등)은 별도 문서에 정리했습니다.

→ **[DECISIONS.md](DECISIONS.md)**

## 테스트

```powershell
uv run pytest -q
```

Ollama 서버나 GPU 없이 실행됩니다 — respx로 Ollama 응답을 목킹하므로 CI(GitHub Actions)에서도 그대로 돕니다. 각 테스트는 실제로 발견됐던 버그 또는 지켜야 할 계약 하나에 대응합니다.

## 알려진 제약

단일 사용자·로컬 환경을 전제로 한 **의도적** 결정입니다(모르고 빠뜨린 것이 아니라, 확장 시 어디를 손대야 하는지까지 [DECISIONS.md](DECISIONS.md)에 정리).

- 인증·권한 없음 — 서버는 `127.0.0.1`에만 바인딩, 데이터는 로컬 SQLite.
- 동시 쓰기 미대응 — 단일 사용자·`NUM_PARALLEL=1`에서 요청이 직렬이므로 불필요.
- 마이그레이션 도구 없음 — `create_all`로 테이블 생성(스키마 진화 시 Alembic 도입).
- Docker로도 Ollama 설치·모델 다운로드는 각 머신에서 필요 (모델은 수 GB라 이미지에 굽지 않음).
- Thinking 모드는 Qwen3 계열 등 추론 과정을 노출하는 모델에서만 동작.
- 스트리밍 도중 브라우저를 닫거나 연결이 끊기면, 생성 중이던 응답은 DB에 저장되지 않습니다.