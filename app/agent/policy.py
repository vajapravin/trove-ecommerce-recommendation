"""Recommendation trigger policy & activity fingerprint cache.

Enforces budget & execution controls:
1. Minimum new events required (`RECO_MIN_NEW_EVENTS`).
2. Minimum elapsed time between agent runs (`RECO_MIN_INTERVAL_MINUTES`).
3. Activity fingerprint hashing: if the hash matches the last stored recommendation's
   fingerprint, LLM execution is skipped entirely (zero-cost repeat visit).
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.agent.runner import run_recommendation_agent
from app.config import get_settings
from app.models import Recommendation
from app.services.activity_summary import UserActivitySummary, summarize_user_activity

logger = logging.getLogger("trove.agent.policy")


def evaluate_trigger_policy(
    db: Session,
    user_id: int,
    force: bool = False,
) -> Tuple[bool, str, UserActivitySummary, Optional[Recommendation]]:
    """Evaluate whether the recommendation agent should execute for user_id.

    Returns:
        (should_run: bool, reason: str, activity_summary: UserActivitySummary, latest_reco: Optional[Recommendation])
    """
    settings = get_settings()
    summary = summarize_user_activity(db, user_id=user_id)

    latest_reco = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == user_id)
        .order_by(Recommendation.created_at.desc())
        .first()
    )

    if force:
        return True, "forced_by_user", summary, latest_reco

    if not latest_reco:
        return True, "initial_recommendation", summary, None

    # Check 1: Fingerprint match (zero-cost cache hit)
    if summary.activity_fingerprint == latest_reco.fingerprint:
        logger.info("Fingerprint match for user_id=%d (%s) — skipping agent", user_id, summary.activity_fingerprint[:12])
        return False, "fingerprint_match_cache_hit", summary, latest_reco

    # Check 2: Minimum new events threshold
    if summary.new_events_count < settings.RECO_MIN_NEW_EVENTS:
        logger.info(
            "Insufficient new events for user_id=%d (%d < %d) — skipping agent",
            user_id, summary.new_events_count, settings.RECO_MIN_NEW_EVENTS
        )
        return False, f"insufficient_new_events ({summary.new_events_count}/{settings.RECO_MIN_NEW_EVENTS})", summary, latest_reco

    # Check 3: Minimum interval between runs
    if latest_reco.created_at:
        now = datetime.now(timezone.utc)
        created_at = latest_reco.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        elapsed_minutes = (now - created_at).total_seconds() / 60.0

        if elapsed_minutes < settings.RECO_MIN_INTERVAL_MINUTES:
            logger.info(
                "Recommendation interval throttle for user_id=%d (%.1fm < %dm) — skipping agent",
                user_id, elapsed_minutes, settings.RECO_MIN_INTERVAL_MINUTES
            )
            return (
                False,
                f"interval_throttled ({elapsed_minutes:.1f}m < {settings.RECO_MIN_INTERVAL_MINUTES}m)",
                summary,
                latest_reco,
            )

    return True, "policy_passed", summary, latest_reco


def run_agent_if_triggered(
    db: Session,
    user_id: int,
    source: str = "web",
    force: bool = False,
) -> Tuple[Recommendation, bool, str]:
    """Check trigger policy and execute agent if conditions are met.

    Returns:
        (recommendation: Recommendation, executed: bool, reason: str)
    """
    should_run, reason, summary, latest_reco = evaluate_trigger_policy(db, user_id, force=force)

    if should_run:
        logger.info("Trigger policy passed for user_id=%d (reason=%s); running agent", user_id, reason)
        reco = run_recommendation_agent(db, user_id, source=source)
        return reco, True, reason

    logger.info("Trigger policy skipped agent for user_id=%d (reason=%s); returning latest reco", user_id, reason)
    assert latest_reco is not None  # Guaranteed by evaluate_trigger_policy logic
    return latest_reco, False, reason
