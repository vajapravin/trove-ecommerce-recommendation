"""User-facing catalog: browse, search, product detail."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import vector_store
from app.database import get_db
from app.deps import current_user
from app.models import Product, User


router = APIRouter(tags=["catalog"])
templates = Jinja2Templates(directory="app/templates")


VALID_LEVELS = {"beginner", "intermediate", "advanced"}


@router.get("/catalog")
def catalog(
    request: Request,
    q: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
):
    """List products with pagination and search/filtering."""
    if level and level not in VALID_LEVELS:
        level = None

    per_page = 40
    offset = (page - 1) * per_page
    products: list[Product] = []
    total_products = 0

    if q:
        where: dict = {}
        clauses = []
        if category:
            clauses.append({"category": category})
        if level:
            clauses.append({"level": level})
        if len(clauses) == 1:
            where = clauses[0]
        elif len(clauses) > 1:
            where = {"$and": clauses}

        try:
            hits = vector_store.query_products(q, n_results=100, where=where or None)
        except Exception:
            hits = []

        if hits:
            total_products = len(hits)
            page_hits = hits[offset:offset + per_page]
            ids = [h["product_id"] for h in page_hits]
            found = {
                p.id: p
                for p in db.query(Product)
                .filter(Product.id.in_(ids), Product.is_active == True)  # noqa: E712
                .all()
            }
            products = [found[i] for i in ids if i in found]
    else:
        query = db.query(Product).filter(Product.is_active == True)  # noqa: E712
        if category:
            query = query.filter(Product.category == category)
        if level:
            query = query.filter(Product.level == level)
        total_products = query.count()
        products = query.order_by(Product.created_at.desc()).offset(offset).limit(per_page).all()

    categories = [
        row[0]
        for row in db.query(Product.category)
        .filter(Product.is_active == True)  # noqa: E712
        .distinct()
        .order_by(Product.category)
        .all()
    ]


    total_pages = max(1, (total_products + per_page - 1) // per_page)

    return templates.TemplateResponse(
        request,
        "catalog.html",
        {
            "user": user,
            "products": products,
            "q": q or "",
            "category": category or "",
            "level": level or "",
            "categories": categories,
            "levels": ["beginner", "intermediate", "advanced"],
            "page": page,
            "total_pages": total_pages,
            "total_products": total_products,
        },
    )



@router.get("/products/{product_id}")
def product_detail(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
):
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")

    # "You might also like" — pure Chroma kNN, no LLM call.
    related: list[Product] = []
    try:
        hits = vector_store.related_products(product.id, n_results=4)
        if hits:
            ids = [h["product_id"] for h in hits]
            found = {
                p.id: p
                for p in db.query(Product)
                .filter(Product.id.in_(ids), Product.is_active == True)  # noqa: E712
                .all()
            }
            related = [found[i] for i in ids if i in found]
    except Exception:
        # Best-effort: never break product page if Chroma is unavailable.
        related = []

    return templates.TemplateResponse(
        request,
        "product.html",
        {"user": user, "product": product, "related": related},
    )
