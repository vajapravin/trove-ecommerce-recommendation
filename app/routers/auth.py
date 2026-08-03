"""Login, registration, and logout."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import create_session_token, hash_password, verify_password
from app.config import get_settings
from app.database import get_db
from app.deps import current_user
from app.models import User


router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
@router.get("/login")
def login_form(request: Request, user: User | None = Depends(current_user)):
    if user:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "login.html", {"error": None, "user": None})


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid email or password.", "user": None},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    token = create_session_token(user.id)
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return response


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
@router.get("/register")
def register_form(request: Request, user: User | None = Depends(current_user)):
    if user:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "register.html", {"error": None, "user": None})


@router.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    email_norm = email.lower().strip()
    err: str | None = None
    if not email_norm or "@" not in email_norm:
        err = "Please enter a valid email address."
    elif len(password) < 6:
        err = "Password must be at least 6 characters."
    elif password != password_confirm:
        err = "Passwords do not match."
    elif db.query(User).filter(User.email == email_norm).first():
        err = "An account with that email already exists."

    if err:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": err, "user": None},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = User(email=email_norm, password_hash=hash_password(password), role="user")
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_session_token(user.id)
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return response


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    return response
