"""Dual-write coordinator for products.

Contract:
    - SQLite is the *source of truth* (transactional).
    - Chroma is a searchable projection kept in sync.

Strategy:
    1. Write to SQLite inside a transaction.
    2. Try to project to Chroma. If Chroma raises, roll back the SQL commit
       so we don't end up with a product visible in the catalog but invisible
       to search (or vice versa).

This is a hackathon-scoped implementation: for production you would push the
projection to a background job with retry, and reconcile with a periodic
sweeper. The interface below hides that detail from the routers.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app import vector_store
from app.models import Product


def create_product(db: Session, **fields) -> Product:
    """Create a Product and mirror it into Chroma."""
    product = Product(**fields)
    db.add(product)
    db.flush()  # populate product.id without committing

    try:
        vector_store.upsert_product(
            product.id,
            title=product.title,
            description=product.description,
            category=product.category,
            level=product.level,
            price=product.price,
            tags=product.tags,
        )
    except Exception:
        db.rollback()
        raise

    db.commit()
    db.refresh(product)
    return product


def bulk_create_products(db: Session, items: list[dict]) -> list[Product]:
    """Bulk create multiple products in SQLite and Chroma atomically."""
    if not items:
        return []
    import json
    prod_objects = []
    for item in items:
        item_copy = dict(item)
        if "images" in item_copy and isinstance(item_copy["images"], list):
            imgs = item_copy.pop("images")
            if "images_json" not in item_copy:
                item_copy["images_json"] = json.dumps(imgs)
            if ("image_url" not in item_copy or not item_copy["image_url"]) and imgs:
                item_copy["image_url"] = imgs[0]
        prod_objects.append(Product(**item_copy))

    db.add_all(prod_objects)
    db.flush()

    vector_items = [
        {
            "product_id": p.id,
            "title": p.title,
            "description": p.description,
            "category": p.category,
            "level": p.level,
            "price": p.price,
            "tags": p.tags,
        }
        for p in prod_objects
    ]

    try:
        vector_store.bulk_upsert_products(vector_items)
    except Exception:
        db.rollback()
        raise

    db.commit()
    return prod_objects




def update_product(db: Session, product: Product, **fields) -> Product:
    """Patch a Product and re-upsert it into Chroma."""
    for key, value in fields.items():
        if hasattr(product, key) and value is not None:
            setattr(product, key, value)
    db.flush()

    try:
        vector_store.upsert_product(
            product.id,
            title=product.title,
            description=product.description,
            category=product.category,
            level=product.level,
            price=product.price,
            tags=product.tags,
        )
    except Exception:
        db.rollback()
        raise

    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product: Product) -> None:
    """Remove from both stores. Chroma first — if that fails we haven't
    committed the SQL delete yet, so we bail out cleanly."""
    pid = product.id
    try:
        vector_store.delete_product(pid)
    except Exception:
        raise
    db.delete(product)
    db.commit()


def reindex_all(db: Session) -> int:
    """Rebuild the Chroma index from SQLite. Useful after a schema change."""
    products = db.query(Product).filter(Product.is_active == True).all()  # noqa: E712
    for p in products:
        vector_store.upsert_product(
            p.id,
            title=p.title,
            description=p.description,
            category=p.category,
            level=p.level,
            price=p.price,
            tags=p.tags,
        )
    return len(products)
