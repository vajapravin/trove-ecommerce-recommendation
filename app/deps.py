"""Request-level dependencies."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth import read_session_token
from app.config import get_settings
from app.database import get_db
from app.models import User


settings = get_settings()


def current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Return the logged-in user, or None if there's no valid session."""
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        return None
    uid = read_session_token(token)
    if uid is None:
        return None
    return db.get(User, uid)


def require_user(user: Optional[User] = Depends(current_user)) -> User:
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required",
            headers={"Location": "/login"},
        )
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user
