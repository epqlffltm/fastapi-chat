# app/main.py

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

2026-07-11
챗봇 서버 - 라우터 분리

2026-07-13
시작 시 자동 생성 연결

2026-07-14
DB 초기화 실행 버그 수정
'''

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.config import BASE_DIR
from app.database.database import init_db,engine
from app.routers import chat, pages, sessions

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 애플리케이션 시작 시 DB 테이블 생성
    await init_db()
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)

app.include_router(pages.router)
app.include_router(chat.router)
app.include_router(sessions.router)