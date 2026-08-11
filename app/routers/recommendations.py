"""User-facing recommendations view + refresh endpoint.

Renders user recommendations and triggers the LangGraph agent state machine.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request, responses, status
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.agent.policy import run_agent_if_triggered
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
    # Run trigger policy: generates if user has no recommendation or if conditions pass
    latest, executed, reason = run_agent_if_triggered(db, user.id, source="web", force=False)

    products: list[Product] = []
    if latest and latest.product_ids_json:
        try:
            product_ids = json.loads(latest.product_ids_json)
            found = {
                p.id: p
                for p in db.query(Product)
                .filter(Product.id.in_(product_ids), Product.is_active == True)  # noqa: E712
                .all()
            }
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
            "executed": executed,
            "reason": reason,
        },
    )


@router.post("/recommendations/refresh")
def refresh_recommendations(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Force trigger the recommendation agent and redirect back to view."""
    run_agent_if_triggered(db, user.id, source="web", force=True)
    return responses.RedirectResponse(
        url="/recommendations",
        status_code=status.HTTP_303_SEE_OTHER,
    )
