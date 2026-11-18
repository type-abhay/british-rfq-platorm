"""
ORM models for the British Auction RFQ System.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RfqStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"       # now < bid_start_at
    ACTIVE = "ACTIVE"             # bid_start_at <= now < current_close_at and < forced_close_at
    CLOSED = "CLOSED"             # reached current_close_at naturally (< forced_close_at)
    FORCE_CLOSED = "FORCE_CLOSED" # reached forced_close_at


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

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    config: Mapped["AuctionConfig"] = relationship(
        back_populates="rfq", uselist=False, cascade="all, delete-orphan"
    )
    bids: Mapped[list["Bid"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan"
    )
    events: Mapped[list["AuctionEvent"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan"
    )


class AuctionConfig(Base):
    __tablename__ = "auction_configs"

    rfq_id: Mapped[str] = mapped_column(ForeignKey("rfqs.id"), primary_key=True)
    trigger_window_minutes: Mapped[int] = mapped_column(Integer)   # X
    extension_minutes: Mapped[int] = mapped_column(Integer)        # Y
    trigger_type: Mapped[str] = mapped_column(String)              # BID_RECEIVED | ANY_RANK_CHANGE | L1_CHANGE

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
    total_price: Mapped[float] = mapped_column(Float, index=True)

    transit_time_days: Mapped[int] = mapped_column(Integer)
    quote_validity: Mapped[str] = mapped_column(String)

    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    rfq: Mapped["Rfq"] = relationship(back_populates="bids")


class AuctionEvent(Base):
    __tablename__ = "auction_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    rfq_id: Mapped[str] = mapped_column(ForeignKey("rfqs.id"), index=True)
    event_type: Mapped[str] = mapped_column(String)

    bid_id: Mapped[str | None] = mapped_column(ForeignKey("bids.id"), nullable=True)
    old_close_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    new_close_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    rfq: Mapped["Rfq"] = relationship(back_populates="events")
