"""
RFQ routes. Notice how little logic is here — every line either
parses HTTP concerns or calls the repository. That's deliberate: if
you find yourself writing an `if` about bidding rules inside a route
function, it belongs in app/services instead.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories import rfq_repository as repo
from app.repositories.rfq_repository import RfqNotFoundError
from app.schemas import AuctionConfigCreate, RfqCreate, RfqDetail, RfqSummary

router = APIRouter(prefix="/rfqs", tags=["rfqs"])


@router.post("", response_model=RfqSummary, status_code=201)
def create_rfq(payload: RfqCreate, db: Session = Depends(get_db)):
    # Cross-field timing validation already happened inside RfqCreate's
    # model_validator, before this function body even runs.
    rfq = repo.create_rfq(db, payload)
    return RfqSummary(
        id=rfq.id,
        reference_id=rfq.reference_id,
        name=rfq.name,
        current_lowest_bid=None,
        current_close_at=rfq.current_close_at,
        forced_close_at=rfq.forced_close_at,
        status=repo.compute_status(rfq),
    )


@router.get("", response_model=list[RfqSummary])
def list_rfqs(db: Session = Depends(get_db)):
    """Auction Listing Page (spec section 8)."""
    rfqs = repo.list_rfqs(db)
    return [
        RfqSummary(
            id=r.id,
            reference_id=r.reference_id,
            name=r.name,
            current_lowest_bid=repo.current_lowest_bid(r),
            current_close_at=r.current_close_at,
            forced_close_at=r.forced_close_at,
            status=repo.compute_status(r),
        )
        for r in rfqs
    ]


@router.get("/{rfq_id}", response_model=RfqDetail)
def get_rfq(rfq_id: str, db: Session = Depends(get_db)):
    """Auction Details Page (spec section 8): bids sorted by price,
    supplier ranking, config, and the full activity log."""
    try:
        rfq = repo.get_rfq_detail(db, rfq_id)
    except RfqNotFoundError:
        raise HTTPException(status_code=404, detail="RFQ not found")

    from app.services.ranking_service import rank_suppliers
    from app.repositories.rfq_repository import _to_bid_records
    from app.schemas import AuctionEventOut, BidOut

    ranked_supplier_ids = rank_suppliers(_to_bid_records(rfq.bids))
    rank_by_supplier = {sid: i + 1 for i, sid in enumerate(ranked_supplier_ids)}

    bids_out = [
        BidOut(
            id=b.id, supplier_id=b.supplier_id, supplier_name=b.supplier_name,
            carrier_name=b.carrier_name, freight_charges=b.freight_charges,
            origin_charges=b.origin_charges, destination_charges=b.destination_charges,
            total_price=b.total_price, transit_time_days=b.transit_time_days,
            quote_validity=b.quote_validity, submitted_at=b.submitted_at,
            rank=rank_by_supplier.get(b.supplier_id),
        )
        for b in sorted(rfq.bids, key=lambda b: b.total_price)
    ]

    return RfqDetail(
        id=rfq.id, reference_id=rfq.reference_id, name=rfq.name,
        bid_start_at=rfq.bid_start_at, bid_close_at=rfq.bid_close_at,
        current_close_at=rfq.current_close_at, forced_close_at=rfq.forced_close_at,
        status=repo.compute_status(rfq),
        config=AuctionConfigCreate(
            trigger_window_minutes=rfq.config.trigger_window_minutes,
            extension_minutes=rfq.config.extension_minutes,
            trigger_type=rfq.config.trigger_type,
        ),
        bids=bids_out,
        events=[AuctionEventOut.model_validate(e) for e in sorted(rfq.events, key=lambda e: e.created_at)],
    )


@router.delete("/{rfq_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rfq(rfq_id: str, db: Session = Depends(get_db)):
    repo.delete_rfq(db, rfq_id=rfq_id)
    return None
