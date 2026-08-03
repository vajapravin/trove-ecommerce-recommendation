"""Behavioral event ingestion.

Endpoint contract:
    POST /events/ingest
    Body: {"events": [ {event_type, product_id?, path?, session_id?, ts?, payload?}, ... ]}
    Response: 202 Accepted, {"received": N}

Design notes:
    - Returns 202 to signal "queued, not fully processed" — even though the
      insert is synchronous, we don't do any downstream work (agent, embedding,
      etc.) on the request path.
    - Uses ``bulk_save_objects`` for one INSERT round-trip per batch.
    - Ignores unknown fields silently; individual bad rows are skipped.
    - Tolerates anonymous events (user_id can be None) — useful for pre-login
      landing-page tracking that we can associate later if we choose.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user
from app.models import Event, User


router = APIRouter(prefix="/events", tags=["events"])


ALLOWED_EVENT_TYPES = {
    "view_page",
    "view_product",
    "search",
    "click",
    "dwell",
    "add_to_cart",
    "recommendation_impression",
    "recommendation_click",
}


class EventIn(BaseModel):
    event_type: str
    product_id: Optional[int] = None
    path: Optional[str] = Field(default=None, max_length=500)
    session_id: Optional[str] = Field(default=None, max_length=64)
    ts: Optional[str] = None  # client-side ISO timestamp (advisory only)
    payload: Optional[dict[str, Any]] = None


class BatchIn(BaseModel):
    events: list[EventIn]


def _parse_client_ts(ts: Optional[str]) -> datetime:
    if not ts:
        return datetime.now(timezone.utc)
    try:
        # Accept both "…Z" and offset-suffixed ISO forms
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
):
    """Bulk-insert a batch of events."""
    # Accept both JSON and text/plain (sendBeacon uses text/plain by default).
    raw = await request.body()
    if not raw:
        return JSONResponse({"received": 0})
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JSONResponse({"received": 0, "error": "bad payload"}, status_code=400)

    try:
        batch = BatchIn.model_validate(data)
    except Exception:
        return JSONResponse({"received": 0, "error": "invalid schema"}, status_code=400)

    rows: list[Event] = []
    uid = user.id if user else None
    for ev in batch.events:
        if ev.event_type not in ALLOWED_EVENT_TYPES:
            continue
        rows.append(Event(
            user_id=uid,
            session_id=ev.session_id,
            event_type=ev.event_type,
            product_id=ev.product_id,
            path=ev.path,
            payload_json=json.dumps(ev.payload) if ev.payload else None,
            created_at=_parse_client_ts(ev.ts),
        ))

    if rows:
        db.bulk_save_objects(rows)
        db.commit()

    return JSONResponse({"received": len(rows)})
