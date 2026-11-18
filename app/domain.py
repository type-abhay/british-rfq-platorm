"""
Framework-independent domain types.

Deliberately contains NO SQLAlchemy, NO FastAPI, NO Pydantic imports.
This is the vocabulary that app/services/*.py speaks. Keeping it pure
Python (dataclasses + enums + datetime) is what makes the services
testable with plain objects and no database.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TriggerType(str, Enum):
    """
    The three extension policies from the spec (section 6.3).
    Stored as a string column in the DB, but defined here so the
    pure services don't need to import the DB model to reference it.
    """
    BID_RECEIVED = "BID_RECEIVED"           # 6.3(a) — any new bid in the window
    ANY_RANK_CHANGE = "ANY_RANK_CHANGE"     # 6.3(b) — any supplier's rank moves
    L1_CHANGE = "L1_CHANGE"                 # 6.3(c) — only the #1 rank moves


@dataclass(frozen=True)
class BidRecord:
    """
    A minimal, immutable view of a bid — only what the ranking and
    extension logic actually need. Frozen because a past bid should
    never be mutated after the fact; a new bid is a new BidRecord.
    """
    supplier_id: str
    total_price: float
    submitted_at: datetime


@dataclass(frozen=True)
class AuctionConfig:
    """Mirrors the `auction_configs` table, but as a plain value object."""
    trigger_window_minutes: int   # X
    extension_minutes: int        # Y
    trigger_type: TriggerType


@dataclass(frozen=True)
class ExtensionDecision:
    """
    The output of ExtensionService.evaluate(). A value object, not an
    ORM row — the repository layer decides how (or whether) to persist
    this; the service layer only decides WHAT should happen.
    """
    extended: bool
    new_close_at: datetime
    reason: str | None = None
