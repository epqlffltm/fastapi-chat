#app/config.py
'''
2026-07-11
.env, 시스템 프롬프트 로딩

2026-07-13
DB연결

2026-07-14
token기반으로 변경
'''

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / "config" / ".env")

# --- DB 해결 ---
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL is None:
    data_dir = BASE_DIR / "data"
    data_dir.mkdir(exist_ok=True)   # 폴더가 없으면 생성 → SQLite가 파일을 만들 수 있게 됨
    DATABASE_URL = f"sqlite:///{(data_dir / 'chat.db').as_posix()}"

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_URL = f"{OLLAMA_HOST}/api/chat"
OLLAMA_TAGS_URL = f"{OLLAMA_HOST}/api/tags"

NUM_THREAD = int(os.getenv("NUM_THREAD", "8"))

MAX_HISTORY_MESSAGES = 30          # 최대 메시지 개수 (안전장치)
MAX_CONTEXT_TOKENS = 8192          # 모델이 사용할 수 있는 최대 컨텍스트 토큰 수
RESERVED_TOKENS = 1024             # 응답 + 시스템 프롬프트용으로 남겨둘 토큰 수

# --- 시스템 프롬프트 해결 ---
def _load_system_prompt() -> str:
    candidates = [
        BASE_DIR / "prompts" / "system_prompt.txt",          # 개인 프롬프트 (gitignore 유지)
        BASE_DIR / "prompts" / "system_prompt.example.txt",  # 저장소에 커밋되는 기본값
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8-sig").strip()
    return "당신은 유능하고 친절한 AI 어시스턴트입니다. 한국어로 답변하세요."

SYSTEM_PROMPT = _load_system_prompt()