# fastapi-chat

FastAPI와 [Ollama](https://ollama.com)를 이용해 로컬 LLM을 서빙하는 채팅 애플리케이션입니다. GPU/CPU 환경에서 여러 모델을 자유롭게 전환하며 대화할 수 있고, 대화 기록은 SQLite에 저장되어 세션 단위로 관리됩니다.

<!-- TODO: 데모 GIF — ScreenToGif로 "질문 입력 → thinking 접힘 → 토큰 스트리밍 → 표 렌더링" 흐름을 10초 내외로 녹화해 docs/demo.gif로 저장 후 아래 주석 해제
![demo](docs/demo.gif)
-->

## 주요 기능

- **멀티 모델 지원**: 로컬에 설치된 Ollama 모델을 드롭다운에서 실시간으로 전환
- **스트리밍 응답**: NDJSON 프로토콜로 토큰 단위 실시간 출력 (타이핑 애니메이션)
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
| DB | SQLite + SQLAlchemy |
| 패키지 관리 | [uv](https://docs.astral.sh/uv/) |
| 프론트엔드 | Vanilla JS / HTML / CSS (프레임워크 없음) |
| LLM 서빙 | Ollama (로컬) |

## 아키텍처

```
app/
├── main.py                  # FastAPI 앱 조립, 라우터 연결
├── config.py                # .env·시스템 프롬프트 로딩, DB 경로 준비
├── ollama_client.py         # Ollama API 스트리밍 통신
├── database/
│   ├── database.py          # SQLAlchemy 엔진/세션, 테이블 자동 생성
│   └── models.py            # ChatSession, ChatMessage 테이블 정의
├── schemas/
│   ├── chat.py              # 채팅 요청 스키마
│   └── session.py           # 세션/메시지 요청·응답 스키마
└── routers/
    ├── pages.py             # 화면 렌더링 (GET /)
    ├── chat.py              # 채팅 API (GET /models, POST /chat)
    └── sessions.py          # 세션 CRUD·검색 API

templates/
└── index.html               # 메인 화면 (Jinja2)

static/
├── css/style.css            # 전체 스타일
└── js/
    ├── session-store.js     # 세션 목록/전환/검색 상태 관리
    ├── message-render.js    # 메시지·코드블록·표 렌더링
    ├── chat-actions.js      # 스트리밍 요청, 수정/재시도
    └── app.js               # 진입점, 이벤트 바인딩

config/
├── .env                     # 로컬 환경변수 (git 미포함)
└── .env.example             # 환경변수 예시

prompts/
├── system_prompt.txt            # 개인 시스템 프롬프트 (git 미포함, 선택)
└── system_prompt.example.txt    # 기본 시스템 프롬프트 (폴백용)

data/
└── chat.db                  # SQLite DB (git 미포함, 첫 실행 시 자동 생성)

pull_models.py               # Ollama 모델 일괄 다운로드 스크립트
```

### 요청 흐름

```
브라우저 (JS)
   │  POST /chat  { session_id, message, model, think }
   ▼
FastAPI (routers/chat.py)
   │  1. 사용자 메시지를 DB에 저장
   │  2. 최근 대화 기록(MAX_HISTORY) 조회
   │  3. Ollama에 스트리밍 요청
   ▼
Ollama (/api/chat, stream=True)
   │  토큰 단위로 thinking / content 청크 전송
   ▼
FastAPI가 NDJSON으로 중계하며 응답 전문을 누적
   │  {"type": "thinking" | "content" | "error", "text": "..."}
   ▼
브라우저가 실시간 렌더링
   (스트림 완료 시점에 FastAPI가 누적된 응답을 DB에 저장하고,
    브라우저는 DB 기준으로 메시지 목록을 재동기화)
```

## 설계 결정

- **SQLite를 선택한 이유**: 이 앱은 로컬 단일 사용자 환경(개인 PC)에서 동작하는 걸 전제로 설계했습니다. PostgreSQL/MariaDB처럼 별도 서버 프로세스를 관리할 필요 없이, 파일 하나로 완결되는 SQLite가 운영 부담 없이 딱 맞는 선택이라고 판단했습니다. SQLAlchemy를 사용하므로 다중 사용자 환경으로 확장이 필요해지면 연결 문자열만 교체해 PostgreSQL 등으로 전환할 수 있습니다.
- **NDJSON 스트리밍 프로토콜**: 응답이 완성될 때까지 기다리는 방식은 CPU 추론 환경에서 체감 대기 시간이 길고, 긴 응답에서는 타임아웃 위험도 있었습니다. 토큰 단위 스트리밍으로 전환하면서 `thinking`/`content`/`error` 세 종류의 이벤트를 구분해 보내야 했기 때문에, 순수 텍스트 스트림 대신 한 줄당 JSON 객체 하나를 보내는 NDJSON 형식을 택했습니다. 표준 대안인 SSE도 검토했지만, EventSource API는 GET 요청만 지원해 채팅 페이로드를 POST body로 실을 수 없었고, fetch 스트림 위에서 SSE 프레이밍을 수동 파싱할 바에는 한 줄이 곧 `JSON.parse` 한 번인 NDJSON이 더 단순하다고 판단했습니다.
- **직접 구현한 경량 렌더러**: 렌더링에 필요한 것이 코드 블록과 표뿐이어서, 마크다운 라이브러리 대신 정규식 기반 파서를 직접 구현했습니다. 모델 출력은 모두 `textContent`로 DOM에 삽입하고 표·코드 블록도 DOM API로 조립하기 때문에, 모델이 어떤 HTML/스크립트를 생성하더라도 실행되지 않습니다(XSS 안전).
- **라우터 분리**: 화면 렌더링(`pages`), 채팅(`chat`), 세션 관리(`sessions`)를 별도 라우터로 나누고, Pydantic 스키마도 `schemas/`로 분리해 요청·응답 형태와 라우트 로직을 구분했습니다.

## 시작하기

### 요구 사항

- Python 3.13
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Ollama](https://ollama.com/download) (로컬에 설치 및 실행 중이어야 함)

### 설치

```powershell
git clone https://github.com/epqlffltm/fastapi-chat.git
cd fastapi-chat
uv sync
```

### 환경 설정 (선택)

별도 설정 없이 바로 실행할 수 있습니다. 환경변수는 기본값이 적용되고, 시스템 프롬프트는 `prompts/system_prompt.example.txt`가 자동으로 사용되며, DB 파일은 첫 실행 시 `data/chat.db`로 자동 생성됩니다.

직접 커스터마이징하려면 예시 파일을 복사해서 수정합니다.

```powershell
Copy-Item config\.env.example config\.env
Copy-Item prompts\system_prompt.example.txt prompts\system_prompt.txt
```

두 파일 모두 git에 포함되지 않으므로 자유롭게 수정할 수 있습니다.

### 모델 다운로드

Ollama 서버가 실행 중인 상태에서:

```powershell
uv run python pull_models.py
```

`pull_models.py`의 `MODELS` 리스트를 원하는 모델로 수정해 사용하세요.

### 실행

```powershell
uv run uvicorn app.main:app --reload
```

브라우저에서 `http://localhost:8000` 접속.

## 환경변수

모두 기본값이 있어 설정 없이도 동작합니다.

| 변수 | 설명 | 기본값 |
|---|---|---|
| `OLLAMA_HOST` | Ollama 서버 주소 | `http://localhost:11434` |
| `NUM_THREAD` | CPU 추론 시 사용할 스레드 수 (물리 코어 수 기준 권장) | `8` |
| `CONTEXT_LIMIT` | 컨텍스트 창 상한 (모델 실제값과 min, VRAM 안전장치) | `32768` |
| `CONTEXT_FALLBACK` | `/api/show` 조회 실패 시 컨텍스트 폴백값 | `8192` |
| `RESERVE_FOR_REPLY` | 생성될 응답을 위해 예산에서 떼어둘 토큰 | `2048` |
| `MAX_HISTORY_MESSAGES` | 히스토리로 보낼 최대 메시지 개수 (토큰 예산과 별개인 안전장치) | `40` |
| `DATABASE_URL` | DB 연결 문자열 (미설정 시 `data/chat.db` 자동 사용) | - |

> 히스토리 길이는 개수와 토큰 예산 **둘 다**로 제한됩니다. 실제 컨텍스트 창 크기는
> 모델마다 다르므로 `/api/show` 로 조회하며, 시스템 프롬프트 토큰은 예산에서 별도로
> 차감합니다. 자세한 근거는 [DECISIONS.md](DECISIONS.md) 참고.

## 설계 결정과 의도적 한계

주요 기술 선택의 **근거**(tiktoken 대신 자기보정 추정기를 쓴 이유, 스트리밍 중 DB
커넥션 수명, 실패를 상태 코드로 표현하는 이유 등)와, 이 프로젝트가 **범위에 맞춰
일부러 하지 않은 것**(인증, 다중 사용자, 마이그레이션 등)은 별도 문서에 정리했습니다.

→ **[DECISIONS.md](DECISIONS.md)**

## 테스트

```powershell
uv run pytest -q
```

Ollama 서버나 GPU 없이 실행됩니다 — respx 로 Ollama 응답을 가짜화하므로 CI 에서도
그대로 돕니다. 각 테스트는 실제로 발견됐던 버그 또는 지켜야 할 계약 하나에 대응합니다.

## 알려진 제약

단일 사용자·로컬 환경을 전제로 한 **의도적** 결정입니다(모르고 빠뜨린 것이 아니라,
확장 시 어디를 손대야 하는지까지 [DECISIONS.md](DECISIONS.md)에 정리).

- 인증·권한 없음 — 서버는 `127.0.0.1` 에만 바인딩, 데이터는 로컬 SQLite.
- 동시 쓰기 미대응 — 단일 사용자·`NUM_PARALLEL=1` 에서 요청이 직렬이므로 불필요.
- 마이그레이션 도구 없음 — `create_all` 로 테이블 생성(스키마 진화 시 Alembic 도입).
- Thinking 모드는 Qwen3 계열 등 추론 과정을 노출하는 모델에서만 동작.
- 스트리밍 도중 브라우저를 닫거나 연결이 끊기면, 생성 중이던 응답은 DB에 저장되지 않습니다.