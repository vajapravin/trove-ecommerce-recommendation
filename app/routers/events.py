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
from app.models import Event, Product, Recommendation, User



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


@router.get("/live-signal")
def get_live_signal(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
):
    """Return live shopper signal analysis for current user or guest session."""
    sid = request.cookies.get("trove_sid") or request.query_params.get("session_id")

    events: list[Event] = []
    if user:
        events = (
            db.query(Event)
            .filter((Event.user_id == user.id) | (Event.session_id == sid if sid else False))
            .order_by(Event.created_at.desc())
            .limit(40)
            .all()
        )
    elif sid:
        events = (
            db.query(Event)
            .filter(Event.session_id == sid)
            .order_by(Event.created_at.desc())
            .limit(40)
            .all()
        )
    else:
        events = db.query(Event).order_by(Event.created_at.desc()).limit(20).all()

    category_counts: dict[str, int] = {}
    search_queries: list[str] = []
    latest_event_logs: list[dict[str, str]] = []

    for ev in events:
        payload = {}
        if ev.payload_json:
            try:
                payload = json.loads(ev.payload_json)
            except Exception:
                pass

        cat = payload.get("category")
        if cat:
            category_counts[cat] = category_counts.get(cat, 0) + 1

        if ev.event_type == "search":
            q = payload.get("q")
            if q and q not in search_queries:
                search_queries.append(q)

        label = ev.event_type.replace("_", " ").title()
        if ev.event_type == "search" and payload.get("q"):
            label = f"Search: '{payload['q']}'"
        elif cat:
            label = f"{label} in {cat}"
        elif payload.get("label"):
            label = f"{label} ({payload['label']})"

        time_str = ev.created_at.strftime("%H:%M:%S") if ev.created_at else "Just now"
        latest_event_logs.append({
            "type": ev.event_type,
            "label": label,
            "time": time_str
        })

    total_cats = sum(category_counts.values()) or 1
    top_categories = [
        {
            "category": c,
            "count": cnt,
            "percentage": min(100, int((cnt / total_cats) * 100))
        }
        for c, cnt in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:4]
    ]

    total_events = len(events)
    engagement_level = (
        "High Engagement" if total_events >= 8 else ("Moderate Interest" if total_events >= 3 else "Starting Journey")
    )

    if top_categories:
        cats_str = " & ".join([tc["category"] for tc in top_categories[:2]])
        if search_queries:
            ai_summary = f"Observing active shopper signal in {cats_str} with explicit search interest for '{search_queries[0]}'."
        else:
            ai_summary = f"Strong category affinity detected in {cats_str}. Synthesizing intent for real-time recommendation updates."
    else:
        ai_summary = "Initializing agent live observer. Browse products or search to build your real-time signal fingerprint."

    # Fetch candidate recommended products for the user/session
    reco_prods: list[Product] = []
    if user:
        latest_reco = db.query(Recommendation).filter(Recommendation.user_id == user.id).order_by(Recommendation.id.desc()).first()
        if latest_reco and latest_reco.product_ids_json:
            try:
                pids = json.loads(latest_reco.product_ids_json)
                if pids:
                    found_dict = {
                        p.id: p
                        for p in db.query(Product).filter(Product.id.in_(pids), Product.is_active == True).all()  # noqa: E712
                    }
                    reco_prods = [found_dict[pid] for pid in pids if pid in found_dict]
            except Exception:
                pass

    if not reco_prods and top_categories:
        top_cat_name = top_categories[0]["category"]
        reco_prods = (
            db.query(Product)
            .filter(Product.category == top_cat_name, Product.is_active == True)  # noqa: E712
            .limit(3)
            .all()
        )

    if not reco_prods:
        reco_prods = db.query(Product).filter(Product.is_active == True).order_by(Product.id.desc()).limit(3).all()

    recommended_products_payload = [
        {
            "id": p.id,
            "title": p.title,
            "price": p.price,
            "image_url": p.image_url,
            "category": p.category,
            "level": p.level,
        }
        for p in reco_prods[:3]
    ]

    return JSONResponse({
        "total_events": total_events,
        "engagement_level": engagement_level,
        "top_categories": top_categories,
        "recent_searches": search_queries[:5],
        "latest_events": latest_event_logs[:5],
        "ai_signal_summary": ai_summary,
        "recommended_products": recommended_products_payload,
    })


