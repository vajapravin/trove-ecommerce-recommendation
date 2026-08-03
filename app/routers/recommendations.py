"""User-facing recommendations view + refresh endpoint.

Day 1: fetch the latest stored recommendation. Day 4 adds the agent trigger.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

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
