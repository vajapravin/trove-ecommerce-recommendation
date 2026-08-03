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


@router.get("/catalog")
def catalog(
    request: Request,
    q: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user),
):
    """List products. If `q` is present, use semantic search; otherwise plain listing."""
    products: list[Product] = []
    semantic_hits = []

    if q:
        # Semantic search via Chroma
        try:
            where = {"category": category} if category else None
            semantic_hits = vector_store.query_products(q, n_results=20, where=where)
        except Exception:
            semantic_hits = []
        # Map back to SQL products in the same order (keeping the vector ranking)
        if semantic_hits:
            ids = [h["product_id"] for h in semantic_hits]
            found = {p.id: p for p in db.query(Product).filter(Product.id.in_(ids), Product.is_active == True).all()}  # noqa: E712
            products = [found[i] for i in ids if i in found]
    else:
        query = db.query(Product).filter(Product.is_active == True)  # noqa: E712
        if category:
            query = query.filter(Product.category == category)
        products = query.order_by(Product.created_at.desc()).limit(60).all()

    categories = [row[0] for row in db.query(Product.category).distinct().order_by(Product.category).all()]

    return templates.TemplateResponse(
        request,
        "catalog.html",
        {
            "user": user,
            "products": products,
            "q": q or "",
            "category": category or "",
            "categories": categories,
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
    return templates.TemplateResponse(
        request,
        "product.html",
        {"user": user, "product": product},
    )
