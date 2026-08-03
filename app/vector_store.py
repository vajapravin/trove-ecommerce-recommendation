"""Chroma vector store wrapper.

We use Chroma in persistent mode with an embedding function that routes every
call through Mesh (via ``mesh_client.embed``). Keeping embedding on the Mesh
side means the product index and the query-time embedding always use the
same model — no drift between what was written and what's being searched.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from app.config import get_settings
from app.mesh_client import embed as mesh_embed


class MeshEmbeddingFunction(EmbeddingFunction):
    """Chroma-compatible wrapper that calls Mesh for embeddings."""

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 — Chroma requires this name
        return mesh_embed(list(input))


PRODUCTS_COLLECTION = "products"


@lru_cache(maxsize=1)
def get_client() -> chromadb.ClientAPI:
    settings = get_settings()
    return chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)


@lru_cache(maxsize=1)
def get_products_collection() -> chromadb.Collection:
    return get_client().get_or_create_collection(
        name=PRODUCTS_COLLECTION,
        embedding_function=MeshEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------------------------
# Convenience API used by the dual-write service and the agent
# ---------------------------------------------------------------------------
def _product_document(title: str, description: str, category: str, level: str, tags: Optional[str]) -> str:
    """Compose the text we actually embed for a product.

    We include structural signals (category, level, tags) inline so a semantic
    query like "advanced agentic AI" matches even if those words aren't in the
    free-text description.
    """
    parts = [f"Title: {title}", f"Category: {category}", f"Level: {level}"]
    if tags:
        parts.append(f"Tags: {tags}")
    parts.append(f"Description: {description}")
    return "\n".join(parts)


def upsert_product(
    product_id: int,
    *,
    title: str,
    description: str,
    category: str,
    level: str,
    price: float,
    tags: Optional[str] = None,
) -> None:
    """Insert or replace a product in the vector store."""
    doc = _product_document(title, description, category, level, tags)
    get_products_collection().upsert(
        ids=[str(product_id)],
        documents=[doc],
        metadatas=[{
            "product_id": product_id,
            "title": title,
            "category": category,
            "level": level,
            "price": float(price),
            "tags": tags or "",
        }],
    )


def delete_product(product_id: int) -> None:
    get_products_collection().delete(ids=[str(product_id)])


def query_products(
    query_text: str,
    *,
    n_results: int = 15,
    where: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Semantic search. Returns a list of {product_id, title, category, level, price, distance}."""
    coll = get_products_collection()
    res = coll.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where or None,
    )
    hits: List[Dict[str, Any]] = []
    ids = res.get("ids", [[]])[0] or []
    metas = res.get("metadatas", [[]])[0] or []
    dists = res.get("distances", [[]])[0] or []
    for _id, meta, dist in zip(ids, metas, dists):
        if not meta:
            continue
        hits.append({
            "product_id": int(meta.get("product_id", _id)),
            "title": meta.get("title", ""),
            "category": meta.get("category", ""),
            "level": meta.get("level", ""),
            "price": float(meta.get("price", 0.0)),
            "tags": meta.get("tags", ""),
            "distance": float(dist),
        })
    return hits


def collection_size() -> int:
    return get_products_collection().count()
