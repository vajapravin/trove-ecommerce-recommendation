"""FastAPI application factory and startup lifecycle."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.auth import hash_password
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import Product, User
from app.routers import auth as auth_router
from app.routers import catalog as catalog_router
from app.routers import events as events_router
from app.routers import pages as pages_router
from app.routers import products as products_router
from app.routers import recommendations as recommendations_router


logger = logging.getLogger("trove")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


# ---------------------------------------------------------------------------
# Startup bootstrap
# ---------------------------------------------------------------------------
STARTER_CATALOG: list[dict] = [
    {
        "title": "Agentic AI: Building Autonomous LLM Systems",
        "description": (
            "Design and ship production-grade agentic systems. Covers planning, tool use, "
            "memory, multi-step reasoning with LangGraph, retrieval, and evaluation. Includes "
            "hands-on projects: research agent, coding agent, and an ops copilot."
        ),
        "category": "AI & Agents",
        "level": "advanced",
        "price": 79.0,
        "tags": "agents,langgraph,rag,tool-use,production",
    },
    {
        "title": "RAG in Depth: From Vector Search to Re-Ranking",
        "description": (
            "A practical deep-dive into retrieval augmented generation: chunking strategies, "
            "embedding choice, hybrid search, metadata filtering, re-ranking, and evaluating "
            "grounding quality. Uses Chroma, Qdrant, and Pinecone side by side."
        ),
        "category": "AI & Agents",
        "level": "intermediate",
        "price": 59.0,
        "tags": "rag,vector-db,retrieval,chroma",
    },
    {
        "title": "Foundations of Prompt Engineering",
        "description": (
            "Prompting patterns that actually generalize: few-shot, chain-of-thought, "
            "self-consistency, structured output, and evaluation. Focus on real tasks — "
            "classification, extraction, generation — and how to measure improvement."
        ),
        "category": "AI & Agents",
        "level": "beginner",
        "price": 29.0,
        "tags": "prompting,llm,evaluation",
    },
    {
        "title": "Production FastAPI: From Zero to Ship",
        "description": (
            "Everything you need to run FastAPI in production: async patterns, dependency "
            "injection, background tasks, WebSockets, testing, observability, and deployment "
            "with uvicorn/gunicorn + Docker."
        ),
        "category": "Backend",
        "level": "intermediate",
        "price": 49.0,
        "tags": "fastapi,python,async,deployment",
    },
    {
        "title": "Data Engineering with dbt and Airflow",
        "description": (
            "Build reliable analytics pipelines. Model your warehouse with dbt, orchestrate "
            "with Airflow, and add tests, docs, and CI to your data stack."
        ),
        "category": "Data",
        "level": "intermediate",
        "price": 59.0,
        "tags": "dbt,airflow,warehouse,pipelines",
    },
    {
        "title": "System Design Interview Bootcamp",
        "description": (
            "Frameworks and templates for cracking system design interviews. Practice with "
            "designs for feeds, chat, ride-hailing, streaming, and payment systems."
        ),
        "category": "Interview Prep",
        "level": "advanced",
        "price": 39.0,
        "tags": "system-design,interview,architecture",
    },
    {
        "title": "Deep Learning with PyTorch",
        "description": (
            "Modern deep learning fundamentals — tensors, autograd, CNNs, transformers, "
            "fine-tuning, and mixed-precision training. Ships with runnable notebooks."
        ),
        "category": "AI & Agents",
        "level": "intermediate",
        "price": 69.0,
        "tags": "pytorch,deep-learning,transformers",
    },
    {
        "title": "Kubernetes for Backend Engineers",
        "description": (
            "Everything a backend engineer needs to be productive with Kubernetes: pods, "
            "deployments, services, ingress, secrets, autoscaling, and Helm."
        ),
        "category": "DevOps",
        "level": "intermediate",
        "price": 55.0,
        "tags": "kubernetes,devops,containers",
    },
]


def _bootstrap() -> None:
    """Create tables, seed admin, seed catalog (if enabled and empty)."""
    settings = get_settings()
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        # Admin bootstrap
        admin = db.query(User).filter(User.email == settings.ADMIN_EMAIL.lower()).first()
        if admin is None:
            admin = User(
                email=settings.ADMIN_EMAIL.lower(),
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
            )
            db.add(admin)
            db.commit()
            logger.info("Seeded admin user %s", settings.ADMIN_EMAIL)

        # Ensure images_json column exists in SQLite table
        from app.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE products ADD COLUMN images_json TEXT;"))
                conn.commit()
            except Exception:
                pass

        # Starter catalog (via dual_write so Chroma is populated too)
        if settings.SEED_CATALOG:

            import json
            catalog_file = os.path.join(os.path.dirname(__file__), "starter_catalog.json")
            items = []
            if os.path.exists(catalog_file):
                try:
                    with open(catalog_file, "r", encoding="utf-8") as f:
                        items = json.load(f)
                except Exception as exc:
                    logger.warning("Failed loading starter_catalog.json: %s", exc)

            if not items:
                items = STARTER_CATALOG

            current_count = db.query(Product).count()
            if current_count < len(items):
                from app.services import dual_write
                try:
                    existing_titles = {p.title for p in db.query(Product.title).all()}
                    missing_items = [item for item in items if item["title"] not in existing_titles]
                    if missing_items:
                        dual_write.bulk_create_products(db, missing_items)
                        logger.info("Seeded %d new products into catalog (total now %d)", len(missing_items), db.query(Product).count())

                    # Attach image_url to existing products missing an image
                    no_img_prods = db.query(Product).filter(Product.image_url == None).all()  # noqa: E711
                    if no_img_prods:
                        title_to_item = {item["title"]: item for item in items}
                        updated_count = 0
                        for p in no_img_prods:
                            match_item = title_to_item.get(p.title)
                            if match_item and match_item.get("image_url"):
                                p.image_url = match_item["image_url"]
                                updated_count += 1
                        if updated_count > 0:
                            db.commit()
                            logger.info("Updated %d existing products with image URLs", updated_count)
                except Exception as exc:  # pragma: no cover — best effort
                    logger.exception("Catalog seed/sync failed: %s", exc)




@asynccontextmanager
async def lifespan(app: FastAPI):
    _bootstrap()
    from app.scheduler import init_scheduler, shutdown_scheduler
    init_scheduler()
    yield
    shutdown_scheduler()



# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    app = FastAPI(
        title="Trove",
        description="Agentic e-commerce recommendation platform",
        version="1.0.0",
        lifespan=lifespan,
    )


    # Static files
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Routers
    app.include_router(pages_router.router)
    app.include_router(auth_router.router)
    app.include_router(catalog_router.router)
    app.include_router(events_router.router)
    app.include_router(recommendations_router.router)
    app.include_router(products_router.router)

    return app


app = create_app()
