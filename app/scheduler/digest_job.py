"""Scheduled daily digest job via APScheduler.

Generates proactive recommendations and records mock delivery entries to `digest_logs`.
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session, sessionmaker

from app.agent.policy import run_agent_if_triggered
from app.config import get_settings
from app.database import engine
from app.models import DigestLog, Product, Recommendation, User

logger = logging.getLogger("trove.scheduler")

_scheduler: Optional[BackgroundScheduler] = None


def run_daily_digest(db: Session) -> List[DigestLog]:
    """Execute the daily digest process for all active users."""
    logger.info("Starting daily digest recommendation generation...")
    active_users = db.query(User).filter(User.is_active == True, User.role == "user").all()

    created_logs: List[DigestLog] = []

    for user in active_users:
        try:
            reco, executed, reason = run_agent_if_triggered(db, user.id, source="scheduled", force=False)
            if not reco:
                continue

            product_ids = []
            if reco.product_ids_json:
                try:
                    product_ids = json.loads(reco.product_ids_json)
                except (json.JSONDecodeError, TypeError):
                    product_ids = []

            products = []
            if product_ids:
                prods_found = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()}
                products = [prods_found[pid] for pid in product_ids if pid in prods_found]

            prod_bullets = "\n".join(f"  • {p.title} (${p.price:.0f}) — Category: {p.category}" for p in products)
            if not prod_bullets:
                prod_bullets = "  • Explore our catalog to find exciting courses!"

            subject = "Your Trove Daily Treasure Digest"
            body = (
                f"Hello {user.email.split('@')[0].title()},\n\n"
                f"{reco.narrative}\n\n"
                f"Recommended Picks For You:\n{prod_bullets}\n\n"
                f"Happy Learning!\nThe Trove Team"
            )

            log_entry = DigestLog(
                user_id=user.id,
                recommendation_id=reco.id,
                channel="mock_email",
                subject=subject,
                body=body,
            )
            db.add(log_entry)
            created_logs.append(log_entry)
        except Exception as exc:
            logger.error("Failed to generate digest for user_id=%d: %s", user.id, exc, exc_info=True)

    db.commit()
    logger.info("Daily digest process completed. Created %d digest log entries.", len(created_logs))
    return created_logs


def _run_scheduled_job():
    """Wrapper function invoked by APScheduler creating its own DB session."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        run_daily_digest(db)
    finally:
        db.close()


def init_scheduler() -> BackgroundScheduler:
    """Initialize and start the BackgroundScheduler for daily digest delivery."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    settings = get_settings()
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _run_scheduled_job,
        trigger="cron",
        hour=settings.DIGEST_HOUR,
        minute=settings.DIGEST_MINUTE,
        id="daily_digest_job",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "APScheduler initialized daily digest job at %02d:%02d daily",
        settings.DIGEST_HOUR, settings.DIGEST_MINUTE
    )
    return _scheduler


def shutdown_scheduler():
    """Gracefully shutdown the scheduler on app unload."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler shutdown complete.")
