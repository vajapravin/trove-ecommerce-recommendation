"""ORM models.

The full schema is defined up front so later stages (event ingest, agent,
scheduler) can import their tables without needing schema migrations mid-build.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    """Timezone-aware UTC now — safer default than datetime.utcnow (deprecated)."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)  # "user" | "admin"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    events: Mapped[list["Event"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


# ---------------------------------------------------------------------------
# Products (courses)
# ---------------------------------------------------------------------------
class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(20), default="beginner", nullable=False)  # beginner/intermediate/advanced
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    images_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of image URLs
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # comma-separated
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    events: Mapped[list["Event"]] = relationship(back_populates="product")

    @property
    def images(self) -> list[str]:
        """Return list of all image URLs for this product."""
        if not self.images_json:
            return [self.image_url] if self.image_url else []
        try:
            import json
            parsed = json.loads(self.images_json)
            if isinstance(parsed, list) and parsed:
                return parsed
        except Exception:
            pass
        return [self.image_url] if self.image_url else []



# ---------------------------------------------------------------------------
# Events — behavioral activity stream
# ---------------------------------------------------------------------------
class Event(Base):
    """A single tracked user activity.

    We keep `payload_json` as a plain TEXT column and let the router serialize
    dicts into it — avoids the JSON-column dialect quirks between SQLite and
    Postgres, and reads back trivially with json.loads().
    """
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # view_product | view_page | search | click | dwell | add_to_cart | ...
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    user: Mapped[Optional["User"]] = relationship(back_populates="events")
    product: Mapped[Optional["Product"]] = relationship(back_populates="events")


# Composite index for the most common read pattern: "give me recent events for user X"
Index("ix_events_user_created", Event.user_id, Event.created_at.desc())


# ---------------------------------------------------------------------------
# Recommendations — persisted output of the agent
# ---------------------------------------------------------------------------
class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    product_ids_json: Mapped[str] = mapped_column(Text, nullable=False)  # e.g. "[3, 7, 12]"
    # Hash of the recent activity window that produced this recommendation.
    # Used to short-circuit the agent when nothing meaningful has changed.
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(20), default="web", nullable=False)  # web | scheduled
    interests_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # summary of inferred interests
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="recommendations")


Index("ix_reco_user_created", Recommendation.user_id, Recommendation.created_at.desc())


# ---------------------------------------------------------------------------
# Digest logs — mock delivery destination for the scheduled email/notification
# ---------------------------------------------------------------------------
class DigestLog(Base):
    __tablename__ = "digest_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(20), default="mock_email", nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
