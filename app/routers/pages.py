#app/routers/pages.py

'''
2026-07-11
챗봇 서버 - 페이지 라우터
'''

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from app.config import BASE_DIR, MAX_HISTORY

router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "templates")

@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"title": "Chat", "max_history": MAX_HISTORY}
    )