"""
pull_models.py
Ollama API를 스트리밍으로 호출해 다운로드 진행률을 직접 출력하는 스크립트
"""

import json
import httpx

OLLAMA_PULL_URL = "http://localhost:11434/api/pull"

MODELS = [
    "qwen3.5:4b",           # 4B, CPU 반응성 좋음
    "qwen3:8b",              # 8B, 품질 상위권
    "exaone3.5:7.8b",       # LG, 한국어 특화
    "llama3.1:8b",           # 8B, 범용
    "phi4-mini"              # 3.8B, 추론 특화
]


def format_bytes(n: int) -> str:
    """바이트를 MB/GB 단위로 보기 좋게 변환"""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}GB"
    return f"{n / 1_000_000:.1f}MB"


def print_progress(status: str, completed: int, total: int):
    bar_width = 30
    percent = (completed / total * 100) if total else 0
    filled = int(bar_width * percent / 100)
    bar = "█" * filled + "-" * (bar_width - filled)
    print(
        f"\r{status:<20} [{bar}] {percent:5.1f}% "
        f"({format_bytes(completed)}/{format_bytes(total)})",
        end="",
        flush=True,
    )


def pull_model(model: str):
    print(f"\n==== {model} 다운로드 시작 ====")
    try:
        with httpx.stream(
            "POST",
            OLLAMA_PULL_URL,
            json={"model": model, "stream": True},
            timeout=None,
        ) as response:
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                status = data.get("status", "")

                if "total" in data and "completed" in data:
                    print_progress(status, data["completed"], data["total"])
                else:
                    print(f"\r{status:<60}", end="", flush=True)

                if data.get("status") == "success":
                    print(f"\n✅ {model} 완료")

    except httpx.ConnectError:
        print(f"\n⚠️  Ollama 서버에 연결할 수 없습니다. (모델: {model})")
    except Exception as e:
        print(f"\n⚠️  {model} 다운로드 중 오류: {e}")


def main():
    for model in MODELS:
        pull_model(model)

    print("\n==== 전체 완료 ====")
    with httpx.Client() as client:
        response = client.get("http://localhost:11434/api/tags")
        for m in response.json().get("models", []):
            print(f" - {m['name']}")


if __name__ == "__main__":
    main()