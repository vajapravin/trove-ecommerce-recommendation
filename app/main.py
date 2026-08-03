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

        # Starter catalog (via dual_write so Chroma is populated too)
        if settings.SEED_CATALOG and db.query(Product).count() == 0:
            # We deliberately import inside the function to avoid a startup-time
            # dependency on Mesh: reindexing hits the embeddings API. If MESH_API_KEY
            # isn't set yet, we log and skip.
            if not settings.MESH_API_KEY:
                logger.warning("MESH_API_KEY not set — skipping catalog seed. "
                               "Set it in .env and restart, or add products via the admin UI.")
                return
            from app.services import dual_write
            try:
                for item in STARTER_CATALOG:
                    dual_write.create_product(db, **item)
                logger.info("Seeded %d starter products", len(STARTER_CATALOG))
            except Exception as exc:  # pragma: no cover — best effort
                logger.exception("Catalog seed failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _bootstrap()
    yield


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    app = FastAPI(
        title="Trove",
        description="Agentic course recommendation platform",
        version="0.1.0",
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
