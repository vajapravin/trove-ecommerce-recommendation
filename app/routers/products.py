"""Admin CRUD for products + Mesh API health check."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import vector_store
from app.database import get_db
from app.deps import require_admin
from app.models import Product, User
from app.services import dual_write


router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Products CRUD
# ---------------------------------------------------------------------------
@router.get("/products")
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


@router.post("/products")
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


@router.get("/products/{product_id}/edit")
def edit_product_form(
    product_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return templates.TemplateResponse(
        request,
        "admin_product_edit.html",
        {"user": admin, "product": product},
    )


@router.post("/products/{product_id}/update")
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


@router.post("/products/{product_id}/delete")
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


# ---------------------------------------------------------------------------
# Mesh + Chroma health check — surfaces model/URL/key issues before the agent
# ever runs. Also reports the current Chroma collection size so we can tell
# at a glance whether dual-write has projected everything correctly.
# ---------------------------------------------------------------------------
@router.get("/mesh-health")
def mesh_health(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.config import get_settings
    settings = get_settings()

    embed_ok, embed_msg = vector_store.ping_embed()
    chat_ok, chat_msg = vector_store.ping_chat()
    try:
        vec_count = vector_store.collection_size()
    except Exception as exc:
        vec_count = f"error: {exc}"
    sql_count = db.query(Product).count()

    return templates.TemplateResponse(
        request,
        "admin_health.html",
        {
            "user": admin,
            "mesh_base_url": settings.MESH_BASE_URL,
            "chat_model": settings.MESH_CHAT_MODEL,
            "embed_model": settings.MESH_EMBED_MODEL,
            "embed_ok": embed_ok, "embed_msg": embed_msg,
            "chat_ok": chat_ok, "chat_msg": chat_msg,
            "sql_count": sql_count,
            "vec_count": vec_count,
            "in_sync": sql_count == vec_count if isinstance(vec_count, int) else False,
        },
    )


# ---------------------------------------------------------------------------
# Digest logs view & manual execution trigger
# ---------------------------------------------------------------------------
@router.get("/digests")
def list_digests(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.models import DigestLog
    logs = db.query(DigestLog).order_by(DigestLog.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin_digests.html",
        {"user": admin, "logs": logs},
    )


@router.post("/digests/trigger")
def trigger_digest(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.scheduler import run_daily_digest
    run_daily_digest(db)
    return RedirectResponse("/admin/digests", status_code=status.HTTP_303_SEE_OTHER)

