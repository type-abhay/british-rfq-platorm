"""
RFQ routes: create, list, detail, delete, and demo-seeding.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.domain import TriggerType
from app.repositories import rfq_repository as repo
from app.repositories.rfq_repository import DuplicateReferenceIdError, RfqNotFoundError, _as_utc, _to_bid_records
from app.schemas import (
    AuctionConfigCreate,
    AuctionEventOut,
    BidCreate,
    BidOut,
    RfqCreate,
    RfqDetail,
    RfqSummary,
)
from app.services.ranking_service import rank_suppliers

router = APIRouter(prefix="/rfqs", tags=["rfqs"])


def _to_summary(r) -> RfqSummary:
    return RfqSummary(
        id=r.id,
        reference_id=r.reference_id,
        name=r.name,
        current_lowest_bid=repo.current_lowest_bid(r),
        bid_start_at=r.bid_start_at,
        bid_close_at=r.bid_close_at,
        current_close_at=r.current_close_at,
        forced_close_at=r.forced_close_at,
        pickup_date=r.pickup_date,
        status=repo.compute_status(r),
    )


@router.post("", response_model=RfqSummary, status_code=status.HTTP_201_CREATED)
def create_rfq(payload: RfqCreate, db: Session = Depends(get_db)):
    try:
        rfq = repo.create_rfq(db, payload)
    except DuplicateReferenceIdError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return _to_summary(rfq)


@router.get("", response_model=list[RfqSummary])
def list_rfqs(db: Session = Depends(get_db)):
    rfqs = repo.list_rfqs(db)
    return [_to_summary(r) for r in rfqs]


@router.get("/{rfq_id}", response_model=RfqDetail)
def get_rfq(rfq_id: str, db: Session = Depends(get_db)):
    try:
        rfq = repo.get_rfq_detail(db, rfq_id)
    except RfqNotFoundError:
        raise HTTPException(status_code=404, detail="RFQ not found")

    ranked_supplier_ids = rank_suppliers(_to_bid_records(rfq.bids))
    rank_by_supplier = {sid: i + 1 for i, sid in enumerate(ranked_supplier_ids)}

    # Track each supplier's best (lowest-price, earliest-timestamp) bid id
    best_bid_id_by_supplier: dict[str, str] = {}
    sorted_bids = sorted(rfq.bids, key=lambda b: (b.total_price, _as_utc(b.submitted_at)))
    for b in sorted_bids:
        if b.supplier_id not in best_bid_id_by_supplier:
            best_bid_id_by_supplier[b.supplier_id] = b.id

    bids_out = [
        BidOut(
            id=b.id,
            supplier_id=b.supplier_id,
            supplier_name=b.supplier_name,
            carrier_name=b.carrier_name,
            freight_charges=b.freight_charges,
            origin_charges=b.origin_charges,
            destination_charges=b.destination_charges,
            total_price=b.total_price,
            transit_time_days=b.transit_time_days,
            quote_validity=b.quote_validity,
            submitted_at=b.submitted_at,
            rank=rank_by_supplier.get(b.supplier_id),
            is_best_for_supplier=(best_bid_id_by_supplier.get(b.supplier_id) == b.id),
        )
        for b in sorted_bids
    ]

    return RfqDetail(
        id=rfq.id,
        reference_id=rfq.reference_id,
        name=rfq.name,
        bid_start_at=rfq.bid_start_at,
        bid_close_at=rfq.bid_close_at,
        current_close_at=rfq.current_close_at,
        forced_close_at=rfq.forced_close_at,
        pickup_date=rfq.pickup_date,
        status=repo.compute_status(rfq),
        config=AuctionConfigCreate(
            trigger_window_minutes=rfq.config.trigger_window_minutes,
            extension_minutes=rfq.config.extension_minutes,
            trigger_type=TriggerType(rfq.config.trigger_type),
        ),
        bids=bids_out,
        events=[
            AuctionEventOut.model_validate(e)
            for e in sorted(rfq.events, key=lambda e: _as_utc(e.created_at), reverse=True)
        ],
    )


@router.delete("/{rfq_id}", status_code=status.HTTP_200_OK)
def delete_rfq(rfq_id: str, db: Session = Depends(get_db)):
    try:
        repo.delete_rfq(db, rfq_id=rfq_id)
    except RfqNotFoundError:
        raise HTTPException(status_code=404, detail="RFQ not found")
    return {"message": "RFQ deleted successfully", "id": rfq_id}


@router.post("/seed-demo", response_model=list[RfqSummary], status_code=status.HTTP_201_CREATED)
def seed_demo_rfqs(db: Session = Depends(get_db)):
    """
    Creates sample British Auctions relative to current UTC time so you can
    immediately test live extensions in the UI without manual date math.
    """
    now = datetime.now(timezone.utc)
    suffix = now.strftime("%H%M%S")

    samples = [
        (
            RfqCreate(
                reference_id=f"RFQ-FCL-{suffix}-1",
                name="Mumbai (INNSA) to Rotterdam (NLRTM) - 40ft HC FCL",
                bid_start_at=now - timedelta(minutes=20),
                bid_close_at=now + timedelta(minutes=8),
                forced_close_at=now + timedelta(minutes=25),
                pickup_date=now + timedelta(days=7),
                config=AuctionConfigCreate(
                    trigger_window_minutes=10,
                    extension_minutes=5,
                    trigger_type=TriggerType.L1_CHANGE,
                ),
            ),
            [
                BidCreate(
                    supplier_id="SUP-001",
                    supplier_name="Maersk Global Logistics",
                    carrier_name="Maersk Line",
                    freight_charges=1200.0,
                    origin_charges=150.0,
                    destination_charges=100.0,
                    transit_time_days=18,
                    quote_validity=(now + timedelta(days=14)).strftime("%Y-%m-%d"),
                ),
                BidCreate(
                    supplier_id="SUP-002",
                    supplier_name="MSC Mediterranean Freight",
                    carrier_name="MSC",
                    freight_charges=1120.0,
                    origin_charges=130.0,
                    destination_charges=95.0,
                    transit_time_days=20,
                    quote_validity=(now + timedelta(days=14)).strftime("%Y-%m-%d"),
                ),
            ],
        ),
        (
            RfqCreate(
                reference_id=f"RFQ-AIR-{suffix}-2",
                name="Delhi (INDEL) to Frankfurt (DEFRA) - Pharma Air Cargo",
                bid_start_at=now - timedelta(minutes=15),
                bid_close_at=now + timedelta(minutes=6),
                forced_close_at=now + timedelta(minutes=12),
                pickup_date=now + timedelta(days=3),
                config=AuctionConfigCreate(
                    trigger_window_minutes=10,
                    extension_minutes=5,
                    trigger_type=TriggerType.BID_RECEIVED,
                ),
            ),
            [
                BidCreate(
                    supplier_id="SUP-003",
                    supplier_name="Lufthansa Cargo Partner",
                    carrier_name="Lufthansa Cargo",
                    freight_charges=2400.0,
                    origin_charges=220.0,
                    destination_charges=180.0,
                    transit_time_days=3,
                    quote_validity=(now + timedelta(days=10)).strftime("%Y-%m-%d"),
                ),
            ],
        ),
        (
            RfqCreate(
                reference_id=f"RFQ-LCL-{suffix}-3",
                name="Chennai (INMAA) to Singapore (SGSIN) - Electronics LCL",
                bid_start_at=now - timedelta(minutes=25),
                bid_close_at=now + timedelta(minutes=9),
                forced_close_at=now + timedelta(minutes=30),
                pickup_date=now + timedelta(days=5),
                config=AuctionConfigCreate(
                    trigger_window_minutes=10,
                    extension_minutes=5,
                    trigger_type=TriggerType.ANY_RANK_CHANGE,
                ),
            ),
            [
                BidCreate(
                    supplier_id="SUP-001",
                    supplier_name="Maersk Global Logistics",
                    carrier_name="Maersk Line",
                    freight_charges=650.0,
                    origin_charges=80.0,
                    destination_charges=70.0,
                    transit_time_days=7,
                    quote_validity=(now + timedelta(days=12)).strftime("%Y-%m-%d"),
                ),
                BidCreate(
                    supplier_id="SUP-004",
                    supplier_name="CMA CGM Asia Shipping",
                    carrier_name="CMA CGM",
                    freight_charges=710.0,
                    origin_charges=85.0,
                    destination_charges=75.0,
                    transit_time_days=6,
                    quote_validity=(now + timedelta(days=12)).strftime("%Y-%m-%d"),
                ),
            ],
        ),
    ]

    created = []
    for rfq_payload, bid_list in samples:
        rfq = repo.create_rfq(db, rfq_payload)
        # Place initial bids slightly earlier (outside trigger window) so initial close time is intact
        early_time = rfq_payload.bid_start_at + timedelta(minutes=2)
        for idx, b_payload in enumerate(bid_list):
            repo.submit_bid(db, rfq.id, b_payload, now=early_time + timedelta(minutes=idx))
        rfq_refreshed = repo.get_rfq_detail(db, rfq.id)
        created.append(_to_summary(rfq_refreshed))

    return created
