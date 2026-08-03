"""Password hashing + session cookie helpers.

We keep auth minimal per the brief: email/password login, signed session
cookies via itsdangerous, no OAuth.
"""
from __future__ import annotations

from typing import Optional

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings


_settings = get_settings()
_serializer = URLSafeTimedSerializer(_settings.SECRET_KEY, salt="trove-session")


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
# bcrypt hard-caps input at 72 bytes and modern versions raise on longer input.
# Truncating is the standard workaround; passwords are still comfortably strong.
_BCRYPT_MAX = 72


def hash_password(plain: str) -> str:
    encoded = plain.encode("utf-8")[:_BCRYPT_MAX]
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        encoded = plain.encode("utf-8")[:_BCRYPT_MAX]
        return bcrypt.checkpw(encoded, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Session tokens (signed cookies)
# ---------------------------------------------------------------------------
def create_session_token(user_id: int) -> str:
    """Encode {user_id} into a signed, timestamped token."""
    return _serializer.dumps({"uid": user_id})


def read_session_token(token: str) -> Optional[int]:
    """Return the user_id if the token is valid and not expired, else None."""
    if not token:
        return None
    try:
        data = _serializer.loads(token, max_age=_settings.SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    uid = data.get("uid") if isinstance(data, dict) else None
    return int(uid) if isinstance(uid, int) else None
