"""
Pydantic schemas — the API's public contract.

Deliberately NOT the same classes as app/models.py. Reasons that
matter for this project specifically:

1. `BidCreate` has no `total_price` field — the client sends the raw
   charges, and the server computes the total (see routers/bids.py).
   If we reused the ORM model as the request schema, a malicious or
   buggy client could submit an arbitrary total_price that doesn't
   match the charges, undermining the entire ranking system.

2. `RfqCreate` cross-validates the three timestamps from section 7
   ("Forced Bid Close Time must always be greater than Bid Close
   Time") at the API boundary, via a Pydantic model_validator — so a
   malformed RFQ is rejected with a 422 before any service or
   repository code runs at all.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.domain import TriggerType


# ---------------------------------------------------------------- #
# RFQ creation (spec section 5)                                     #
# ---------------------------------------------------------------- #

class AuctionConfigCreate(BaseModel):
    trigger_window_minutes: int = Field(gt=0, description="X — minutes before close to monitor activity")
    extension_minutes: int = Field(gt=0, description="Y — minutes to extend by when triggered")
    trigger_type: TriggerType


class RfqCreate(BaseModel):
    reference_id: str
    name: str
    bid_start_at: datetime
    bid_close_at: datetime
    forced_close_at: datetime
    pickup_date: datetime
    config: AuctionConfigCreate

    @model_validator(mode="after")
    def _validate_time_ordering(self) -> "RfqCreate":
        # Spec section 7, validation rule 1 & implicit ordering rule.
        if self.bid_close_at <= self.bid_start_at:
            raise ValueError("bid_close_at must be after bid_start_at")
        if self.forced_close_at <= self.bid_close_at:
            raise ValueError("forced_close_at must be after bid_close_at")
        return self


class RfqSummary(BaseModel):
    """Shape for the Auction Listing Page (spec section 8)."""
    id: str
    reference_id: str
    name: str
    current_lowest_bid: float | None
    current_close_at: datetime
    forced_close_at: datetime
    status: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------- #
# Bid submission (spec section 5's "Quote Submission form")         #
# ---------------------------------------------------------------- #

class BidCreate(BaseModel):
    supplier_id: str
    supplier_name: str
    carrier_name: str
    freight_charges: float = Field(ge=0)
    origin_charges: float = Field(ge=0)
    destination_charges: float = Field(ge=0)
    transit_time_days: int = Field(gt=0)
    quote_validity: str
    # Note: total_price is deliberately absent here — see module docstring.


class BidOut(BaseModel):
    id: str
    supplier_id: str
    supplier_name: str
    carrier_name: str
    freight_charges: float
    origin_charges: float
    destination_charges: float
    total_price: float
    transit_time_days: int
    quote_validity: str
    submitted_at: datetime
    rank: int | None = None  # filled in by the router, not stored on the row

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------- #
# Auction Details Page (spec section 8)                             #
# ---------------------------------------------------------------- #

class AuctionEventOut(BaseModel):
    event_type: str
    bid_id: str | None
    old_close_at: datetime | None
    new_close_at: datetime | None
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RfqDetail(BaseModel):
    id: str
    reference_id: str
    name: str
    bid_start_at: datetime
    bid_close_at: datetime
    current_close_at: datetime
    forced_close_at: datetime
    status: str
    config: AuctionConfigCreate
    bids: list[BidOut]
    events: list[AuctionEventOut]

    model_config = {"from_attributes": True}
