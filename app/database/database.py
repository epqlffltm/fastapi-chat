#app/database/database.py

'''
2026-07-13

'''

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL

# SQLite는 기본적으로 하나의 스레드에서만 연결을 쓰도록 강제하는데,
# FastAPI는 요청마다 다른 스레드/태스크를 쓸 수 있어서 이 옵션이 필요함
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():#앱 시작 시 호출 — 테이블이 없으면 생성, 있으면 아무 것도 안 함
    Base.metadata.create_all(bind=engine)