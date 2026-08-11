"""User-facing recommendations view + refresh endpoint.

Renders user recommendations and triggers the LangGraph agent state machine.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request, responses, status
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.agent.runner import run_recommendation_agent
from app.database import get_db
from app.deps import require_user
from app.models import Product, Recommendation, User

router = APIRouter(tags=["recommendations"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/recommendations")
def view_recommendations(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    latest = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == user.id)
        .order_by(Recommendation.created_at.desc())
        .first()
    )

    products: list[Product] = []
    if latest:
        try:
            product_ids = json.loads(latest.product_ids_json)
            found = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()}
            products = [found[i] for i in product_ids if i in found]
        except (json.JSONDecodeError, TypeError):
            products = []

    return templates.TemplateResponse(
        request,
        "recommendations.html",
        {
            "user": user,
            "recommendation": latest,
            "products": products,
        },
    )


@router.post("/recommendations/refresh")
def refresh_recommendations(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Trigger the LangGraph recommendation agent manually and redirect back to view."""
    run_recommendation_agent(db, user.id, source="web")
    return responses.RedirectResponse(
        url="/recommendations",
        status_code=status.HTTP_303_SEE_OTHER,
    )
