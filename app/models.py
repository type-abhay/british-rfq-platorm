"""
ORM models.

Key design decisions, mapped to spec sections:

- RFQ keeps BOTH `bid_close_at` (the original time, immutable — useful
  for reporting "how much did this auction actually extend by") and
  `current_close_at` (the live deadline that ExtensionService moves).
  Conflating these into one column would lose the ability to answer
  "was this auction extended at all?" without replaying the event log.

- AuctionEvent is an append-only log (section 8's "Activity log").
  It is intentionally a separate table from Bid, not a boolean flag on
  Bid, because one bid submission can produce ZERO or ONE extension
  event, and we also log CLOSED/FORCE_CLOSED events that have no
  associated bid at all.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class RfqStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"   # now < bid_start_at
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"             # reached current_close_at naturally (no further extension)
    FORCE_CLOSED = "FORCE_CLOSED" # reached forced_close_at (possibly via extensions)


class EventType(str, enum.Enum):
    BID_SUBMITTED = "BID_SUBMITTED"
    EXTENDED = "EXTENDED"
    CLOSED = "CLOSED"
    FORCE_CLOSED = "FORCE_CLOSED"


class Rfq(Base):
    __tablename__ = "rfqs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    reference_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)

    bid_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    bid_close_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))        # original, immutable
    current_close_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))    # moves with extensions
    forced_close_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))     # hard ceiling, immutable
    pickup_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    config: Mapped["AuctionConfig"] = relationship(back_populates="rfq", uselist=False, cascade="all, delete-orphan")
    bids: Mapped[list["Bid"]] = relationship(back_populates="rfq", cascade="all, delete-orphan")
    events: Mapped[list["AuctionEvent"]] = relationship(back_populates="rfq", cascade="all, delete-orphan")


class AuctionConfig(Base):
    """One-to-one with Rfq. Separate table (not columns on Rfq) because
    it's a cohesive, independently-meaningful unit (section 6's config
    block) and keeps Rfq's own columns focused on timing/identity."""
    __tablename__ = "auction_configs"

    rfq_id: Mapped[str] = mapped_column(ForeignKey("rfqs.id"), primary_key=True)
    trigger_window_minutes: Mapped[int] = mapped_column(Integer)   # X
    extension_minutes: Mapped[int] = mapped_column(Integer)        # Y
    trigger_type: Mapped[str] = mapped_column(String)              # see domain.TriggerType

    rfq: Mapped["Rfq"] = relationship(back_populates="config")


class Bid(Base):
    __tablename__ = "bids"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    rfq_id: Mapped[str] = mapped_column(ForeignKey("rfqs.id"), index=True)
    supplier_id: Mapped[str] = mapped_column(String, index=True)
    supplier_name: Mapped[str] = mapped_column(String)

    carrier_name: Mapped[str] = mapped_column(String)
    freight_charges: Mapped[float] = mapped_column(Float)
    origin_charges: Mapped[float] = mapped_column(Float)
    destination_charges: Mapped[float] = mapped_column(Float)
    # Computed server-side as the sum of the three charges above —
    # never trust a client-supplied total; see schemas.py.
    total_price: Mapped[float] = mapped_column(Float, index=True)

    transit_time_days: Mapped[int] = mapped_column(Integer)
    quote_validity: Mapped[str] = mapped_column(String)

    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    rfq: Mapped["Rfq"] = relationship(back_populates="bids")


class AuctionEvent(Base):
    """Append-only. Rows are never updated or deleted — this table IS
    the audit trail required by section 8 ('Activity log showing bid
    submissions, time extensions, reason for each extension')."""
    __tablename__ = "auction_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    rfq_id: Mapped[str] = mapped_column(ForeignKey("rfqs.id"), index=True)
    event_type: Mapped[str] = mapped_column(String)

    bid_id: Mapped[str | None] = mapped_column(ForeignKey("bids.id"), nullable=True)
    old_close_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    new_close_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    rfq: Mapped["Rfq"] = relationship(back_populates="events")
