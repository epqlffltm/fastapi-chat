#app/config.py
'''
2026-07-11
.env, 시스템 프롬프트 로딩

2026-07-13
DB연결
'''

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / "config" / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{(BASE_DIR / 'data' / 'chat.db').as_posix()}"
)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_URL = f"{OLLAMA_HOST}/api/chat"
OLLAMA_TAGS_URL = f"{OLLAMA_HOST}/api/tags"

NUM_THREAD = int(os.getenv("NUM_THREAD", "8"))
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "14"))

with open(BASE_DIR / "prompts" / "system_prompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read().strip()