"""Top-level page routes (home, health)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.deps import current_user
from app.models import User


router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def home(request: Request, user: User | None = Depends(current_user)):
    if user is None:
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "index.html", {"user": user})


@router.get("/health")
def health():
    return JSONResponse({"status": "ok"})
