#main.py

'''
2026-07-09
test 해본 것
'''

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/img", StaticFiles(directory="templates/img"), name="img")
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"title": "Hello"}
    )