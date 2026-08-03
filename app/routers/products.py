"""Admin CRUD for products.

Day 1: routes wired, using dual_write so both stores stay in sync. Templates
for the admin panel land on Day 2 — until then these endpoints still work over
form-encoded requests.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import Product, User
from app.services import dual_write


router = APIRouter(prefix="/admin/products", tags=["admin-products"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def list_products(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    products = db.query(Product).order_by(Product.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin_products.html",
        {"user": admin, "products": products},
    )


@router.post("")
def create_product(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    level: str = Form("beginner"),
    price: float = Form(0.0),
    tags: str = Form(""),
    image_url: str = Form(""),
):
    dual_write.create_product(
        db,
        title=title.strip(),
        description=description.strip(),
        category=category.strip(),
        level=level.strip(),
        price=float(price),
        tags=tags.strip() or None,
        image_url=image_url.strip() or None,
    )
    return RedirectResponse("/admin/products", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{product_id}/update")
def update_product(
    product_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    level: str = Form("beginner"),
    price: float = Form(0.0),
    tags: str = Form(""),
    image_url: str = Form(""),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    dual_write.update_product(
        db,
        product,
        title=title.strip(),
        description=description.strip(),
        category=category.strip(),
        level=level.strip(),
        price=float(price),
        tags=tags.strip() or None,
        image_url=image_url.strip() or None,
    )
    return RedirectResponse("/admin/products", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{product_id}/delete")
def delete_product(
    product_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    dual_write.delete_product(db, product)
    return RedirectResponse("/admin/products", status_code=status.HTTP_303_SEE_OTHER)
