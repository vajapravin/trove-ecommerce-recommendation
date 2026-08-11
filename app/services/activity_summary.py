"""Activity summary service.

Aggregates raw behavioral events (search, view_product, dwell, add_to_cart, etc.)
for a given user into a structured activity summary (`UserActivitySummary`).
This summary feeds the LangGraph agent's analyze/retrieve nodes and powers the
fingerprint cache for zero-cost repeat visits.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Event, Product, Recommendation


@dataclass
class UserActivitySummary:
    """Structured summary of a user's recent behavior."""

    user_id: int
    total_events: int = 0
    new_events_count: int = 0
    search_queries: List[str] = field(default_factory=list)
    viewed_product_ids: List[int] = field(default_factory=list)
    viewed_product_titles: List[str] = field(default_factory=list)
    interacted_categories: List[str] = field(default_factory=list)
    interacted_levels: List[str] = field(default_factory=list)
    cart_product_ids: List[int] = field(default_factory=list)
    total_dwell_seconds: float = 0.0
    event_ids: List[int] = field(default_factory=list)
    activity_fingerprint: str = ""
    last_event_at: Optional[datetime] = None
    formatted_summary: str = ""


def compute_activity_fingerprint(event_ids: List[int]) -> str:
    """Generate a SHA256 fingerprint from an ordered sequence of event IDs."""
    if not event_ids:
        return "empty_activity"
    raw = ",".join(str(eid) for eid in sorted(event_ids))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def summarize_user_activity(
    db: Session,
    user_id: int,
    limit: int = 50,
) -> UserActivitySummary:
    """Fetch recent events for user_id and return a structured UserActivitySummary.

    Finds the latest recommendation to determine `new_events_count` since the last run.
    """
    # 1. Check when the latest recommendation was created
    latest_reco = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == user_id)
        .order_by(Recommendation.created_at.desc())
        .first()
    )

    # 2. Query recent events for the user
    query = db.query(Event).filter(Event.user_id == user_id)
    events = query.order_by(Event.created_at.desc()).limit(limit).all()

    if not events:
        return UserActivitySummary(
            user_id=user_id,
            formatted_summary="User has no recorded browsing or search activity.",
            activity_fingerprint="empty_activity",
        )

    # Reverse events to process in chronological order
    events_chrono = list(reversed(events))

    # Calculate new events since last recommendation
    if latest_reco and latest_reco.created_at:
        reco_dt = latest_reco.created_at
        if reco_dt.tzinfo is None:
            reco_dt = reco_dt.replace(tzinfo=timezone.utc)

        def _to_utc(dt):
            return dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt

        new_events = [
            e for e in events_chrono
            if e.created_at and _to_utc(e.created_at) > reco_dt
        ]
        new_events_count = len(new_events)
    else:
        new_events_count = len(events_chrono)


    event_ids = [e.id for e in events_chrono]
    fingerprint = compute_activity_fingerprint(event_ids)

    # Load products associated with event product_ids
    product_ids_set = {e.product_id for e in events_chrono if e.product_id is not None}
    products_by_id = {}
    if product_ids_set:
        prods = db.query(Product).filter(Product.id.in_(product_ids_set)).all()
        products_by_id = {p.id: p for p in prods}

    search_queries: List[str] = []
    viewed_product_ids: List[int] = []
    viewed_titles: List[str] = []
    category_counter: Counter[str] = Counter()
    level_counter: Counter[str] = Counter()
    cart_product_ids: List[int] = []
    total_dwell: float = 0.0

    summary_lines: List[str] = []

    for event in events_chrono:
        etype = event.event_type
        payload = {}
        if event.payload_json:
            try:
                payload = json.loads(event.payload_json)
            except (json.JSONDecodeError, TypeError):
                pass

        if etype in ("search", "search_catalog"):
            q = payload.get("query") or payload.get("q")
            if q and q not in search_queries:
                search_queries.append(q)
                summary_lines.append(f"- Searched catalog for: '{q}'")


        elif etype in ("view_product", "click"):
            pid = event.product_id or payload.get("product_id")
            if pid:
                pid = int(pid)
                if pid not in viewed_product_ids:
                    viewed_product_ids.append(pid)
                p = products_by_id.get(pid)
                if p:
                    if p.title not in viewed_titles:
                        viewed_titles.append(p.title)
                    category_counter[p.category] += 1
                    level_counter[p.level] += 1
                    summary_lines.append(f"- Viewed product: '{p.title}' (Category: {p.category}, Level: {p.level})")

        elif etype == "dwell":
            dur = float(payload.get("duration", 0.0) or payload.get("dwell_time", 0.0) or 0.0)
            total_dwell += dur

        elif etype == "add_to_cart":
            pid = event.product_id or payload.get("product_id")
            if pid:
                pid = int(pid)
                if pid not in cart_product_ids:
                    cart_product_ids.append(pid)
                p = products_by_id.get(pid)
                p_name = p.title if p else f"Product #{pid}"
                summary_lines.append(f"- Added to cart: '{p_name}'")

    # Order categories & levels by frequency
    top_categories = [cat for cat, _ in category_counter.most_common()]
    top_levels = [lvl for lvl, _ in level_counter.most_common()]

    # Format human/LLM readable text
    if not summary_lines:
        formatted = "User visited pages but did not perform specific searches or view products."
    else:
        formatted = "Recent user behavior summary:\n" + "\n".join(summary_lines[-15:])

    return UserActivitySummary(
        user_id=user_id,
        total_events=len(events_chrono),
        new_events_count=new_events_count,
        search_queries=search_queries,
        viewed_product_ids=viewed_product_ids,
        viewed_product_titles=viewed_titles,
        interacted_categories=top_categories,
        interacted_levels=top_levels,
        cart_product_ids=cart_product_ids,
        total_dwell_seconds=total_dwell,
        event_ids=event_ids,
        activity_fingerprint=fingerprint,
        last_event_at=events_chrono[-1].created_at if events_chrono else None,
        formatted_summary=formatted,
    )
