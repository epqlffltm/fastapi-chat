# syntax=docker/dockerfile:1

# ── 빌드 스테이지 ─────────────────────────────────────────
# uv 공식 이미지에서 의존성만 설치한다. 빌드 도구를 최종 이미지에 남기지 않으려고
# 멀티스테이지로 나눈다 (이미지 크기 ↓).
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# 의존성 정의만 먼저 복사 → 이 파일들이 안 바뀌면 Docker가 캐시를 재사용해
# 소스만 고칠 때 install을 건너뛴다 (빌드 ↑).
COPY pyproject.toml uv.lock ./

# uv.lock 을 그대로 지켜 설치 (재현성). dev 그룹(pytest 등)은 런타임에 불필요하므로 제외.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project


# ── 런타임 스테이지 ───────────────────────────────────────
# uv 없이, 파이썬 슬림 이미지에 위에서 만든 .venv 와 소스만 얹는다.
FROM python:3.13-slim-bookworm

WORKDIR /app

# 가상환경을 빌더에서 통째로 가져온다.
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# 애플리케이션 소스. (.dockerignore 가 .venv/.git/data 등을 제외한다.)
COPY app ./app
COPY templates ./templates
COPY static ./static
COPY prompts ./prompts

# 컨테이너 밖에서 넣지 않으면 쓸 기본값.
# OLLAMA_HOST: 컨테이너의 localhost 는 호스트가 아니다. host.docker.internal 로 호스트의
#              Ollama(GPU)를 가리킨다. compose 에서 다시 지정하지만 단독 실행 대비 기본값도 둔다.
ENV OLLAMA_HOST=http://host.docker.internal:11434 \
    DATABASE_URL=sqlite:////app/data/chat.db

EXPOSE 8000

# --reload 없음: 운영/배포용. 개발 시엔 compose 로 소스를 마운트하거나 로컬에서 uv run.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
