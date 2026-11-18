"""
Pydantic schemas — the API's public contract.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.domain import TriggerType


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
    bid_start_at: datetime
    bid_close_at: datetime
    current_close_at: datetime
    forced_close_at: datetime
    pickup_date: datetime
    status: str

    model_config = {"from_attributes": True}


class BidCreate(BaseModel):
    supplier_id: str
    supplier_name: str
    carrier_name: str
    freight_charges: float = Field(ge=0)
    origin_charges: float = Field(ge=0)
    destination_charges: float = Field(ge=0)
    transit_time_days: int = Field(gt=0)
    quote_validity: str


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
    rank: int | None = None
    is_best_for_supplier: bool = False

    model_config = {"from_attributes": True}


class AuctionEventOut(BaseModel):
    id: str | None = None
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
    pickup_date: datetime
    status: str
    config: AuctionConfigCreate
    bids: list[BidOut]
    events: list[AuctionEventOut]

    model_config = {"from_attributes": True}
