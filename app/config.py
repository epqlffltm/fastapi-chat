# app/config.py
"""
2026-07-11
.env, 시스템 프롬프트 로딩

2026-07-13
DB연결

2026-07-14
token기반으로 변경

2026-07-15
tiktoken 제거. 컨텍스트 길이를 하드코딩하지 않고 Ollama에서 조회하도록 변경.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / "config" / ".env")

# --- DB ---
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL is None:
    data_dir = BASE_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    DATABASE_URL = f"sqlite:///{(data_dir / 'chat.db').as_posix()}"

# --- Ollama ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_URL = f"{OLLAMA_HOST}/api/chat"
OLLAMA_TAGS_URL = f"{OLLAMA_HOST}/api/tags"
OLLAMA_SHOW_URL = f"{OLLAMA_HOST}/api/show"

NUM_THREAD = int(os.getenv("NUM_THREAD", "8"))

# --- 컨텍스트 예산 ---
#
# 이전엔 MAX_CONTEXT_TOKENS = 8192 를 코드에 박아뒀는데, 실제로는 Ollama가
# VRAM을 보고 컨텍스트를 정한다 (24~48GiB → 32k). RTX 3090 24GB에서 32k를
# 쓸 수 있는데 8k만 쓰고 있었다 = 창의 25%.
#
# 이제는 /api/show 로 모델의 진짜 최대 컨텍스트를 읽어오고, 아래 상한과
# min() 을 취한 값을 num_ctx 로 **명시해서 보낸다**. Ollama가 뭘 골랐는지
# 추측하지 않고, 우리가 정한 값을 알려주는 것이다.
#
# 상한을 두는 이유: 컨텍스트가 클수록 KV 캐시 VRAM이 선형으로 늘어난다.
# 모델 최대치(qwen3:8b = 40960)를 그대로 쓰면 GPU에서 밀려날 수 있다.
CONTEXT_LIMIT = int(os.getenv("CONTEXT_LIMIT", "32768"))

# /api/show 가 실패하거나 context_length 키가 없을 때의 안전한 폴백
CONTEXT_FALLBACK = int(os.getenv("CONTEXT_FALLBACK", "8192"))

# 답변이 쓸 자리. 이만큼은 히스토리로 채우지 않고 비워둔다.
RESERVE_FOR_REPLY = int(os.getenv("RESERVE_FOR_REPLY", "2048"))

# 토큰 예산과 별개인 안전장치. 아무리 짧은 메시지라도 이 개수 이상은 안 보낸다.
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "40"))


# --- 시스템 프롬프트 ---
def _load_system_prompt() -> str:
    candidates = [
        BASE_DIR / "prompts" / "system_prompt.txt",  # 개인 프롬프트 (gitignore)
        BASE_DIR / "prompts" / "system_prompt.example.txt",  # 저장소 기본값
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8-sig").strip()
    return "당신은 유능하고 친절한 AI 어시스턴트입니다. 한국어로 답변하세요."


SYSTEM_PROMPT = _load_system_prompt()
