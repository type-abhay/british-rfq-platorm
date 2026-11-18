"""
RfqRepository: the ONLY place that talks to the database for RFQs/bids.

This is where the concurrency story from our architecture discussion
is actually implemented: `submit_bid` takes out a row lock on the RFQ
BEFORE reading anything else, so two suppliers bidding within
milliseconds of each other are serialized — the second one only
proceeds once the first has fully committed (new bid inserted, any
extension applied). Without this lock, both could read the same
"before" ranking and "before" close time, and compute extension
decisions against data that's already stale by the time either commits.

Everything here is intentionally "dumb": it reads data, calls the
pure services (ranking_service / extension_service) to make decisions,
and writes the result. No business RULES live in this file — only
the mechanics of doing that safely.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, delete, update
from sqlalchemy.orm import Session, selectinload

from app.domain import AuctionConfig as AuctionConfigVO
from app.domain import BidRecord, TriggerType
from app.models import AuctionConfig, AuctionEvent, Bid, EventType, Rfq
from app.schemas import BidCreate, RfqCreate
from app.services.extension_service import evaluate as evaluate_extension
from app.services.ranking_service import rank_suppliers

# imports for bid deletion, purely for developmental processes
from fastapi import HTTPException


class RfqNotFoundError(Exception):
    pass


class BiddingNotOpenError(Exception):
    """Raised when a bid arrives before bid_start_at or after the
    current close / forced close. Kept as its own exception (rather
    than a generic ValueError) so the router can map it to a specific
    HTTP status (409) instead of a generic 400."""
    pass


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

def create_rfq(db: Session, payload: RfqCreate) -> Rfq:
    rfq = Rfq(
        reference_id=payload.reference_id,
        name=payload.name,
        bid_start_at=payload.bid_start_at,
        bid_close_at=payload.bid_close_at,
        current_close_at=payload.bid_close_at,  # starts equal to bid_close_at; moves on extension
        forced_close_at=payload.forced_close_at,
        pickup_date=payload.pickup_date,
    )
    rfq.config = AuctionConfig(
        trigger_window_minutes=payload.config.trigger_window_minutes,
        extension_minutes=payload.config.extension_minutes,
        trigger_type=payload.config.trigger_type.value,
    )
    db.add(rfq)
    db.commit()
    db.refresh(rfq)
    return rfq


def list_rfqs(db: Session) -> list[Rfq]:
    stmt = select(Rfq).options(selectinload(Rfq.bids))
    return list(db.scalars(stmt).all())


def get_rfq_detail(db: Session, rfq_id: str) -> Rfq:
    stmt = (
        select(Rfq)
        .options(selectinload(Rfq.bids), selectinload(Rfq.events), selectinload(Rfq.config))
        .where(Rfq.id == rfq_id)
    )
    rfq = db.scalars(stmt).first()
    if rfq is None:
        raise RfqNotFoundError(rfq_id)
    return rfq


def _to_bid_records(bids: list[Bid]) -> list[BidRecord]:
    return [BidRecord(b.supplier_id, b.total_price, b.submitted_at) for b in bids]


def submit_bid(db: Session, rfq_id: str, payload: BidCreate, now: datetime | None = None) -> Bid:
    """
    The one transactional write path that matters for correctness.

    Steps map 1:1 onto the algorithm we designed earlier:
      1. Lock the RFQ row.
      2. Validate timing against the (freshly-locked, so up-to-date) row.
      3. Snapshot ranking "before".
      4. Insert the bid + log BID_SUBMITTED.
      5. Snapshot ranking "after".
      6. Ask ExtensionService for a decision.
      7. Apply it (update current_close_at + log EXTENDED) if triggered.
      8. Commit — lock releases here.
    """
    now = _as_utc(now or datetime.now(timezone.utc))

    # --- Step 1: lock the row. Everything below reads data that is
    # now guaranteed not to change underneath us until we commit. ---
    stmt = select(Rfq).options(selectinload(Rfq.bids), selectinload(Rfq.config)).where(Rfq.id == rfq_id).with_for_update()
    rfq = db.scalars(stmt).first()
    if rfq is None:
        raise RfqNotFoundError(rfq_id)

    # --- Step 2: timing validation (spec section 5 & 7). ---
    if now < _as_utc(rfq.bid_start_at):
        raise BiddingNotOpenError("Bidding has not started yet.")
    if now >= _as_utc(rfq.current_close_at) or now >= _as_utc(rfq.forced_close_at):
        raise BiddingNotOpenError("Bidding is closed for this RFQ.")

    # --- Step 3: snapshot before. ---
    bids_before = _to_bid_records(rfq.bids)

    # --- Step 4: insert bid + log it. total_price computed here,
    # server-side, from the submitted charges (never trust a client
    # total — see schemas.py docstring). ---
    total_price = payload.freight_charges + payload.origin_charges + payload.destination_charges
    bid = Bid(
        rfq_id=rfq.id,
        supplier_id=payload.supplier_id,
        supplier_name=payload.supplier_name,
        carrier_name=payload.carrier_name,
        freight_charges=payload.freight_charges,
        origin_charges=payload.origin_charges,
        destination_charges=payload.destination_charges,
        total_price=total_price,
        transit_time_days=payload.transit_time_days,
        quote_validity=payload.quote_validity,
        submitted_at=now,
    )
    db.add(bid)
    db.flush()  # assigns bid.id without ending the transaction

    db.add(AuctionEvent(rfq_id=rfq.id, event_type=EventType.BID_SUBMITTED.value, bid_id=bid.id, created_at=now))

    # --- Step 5: snapshot after. ---
    bids_after = bids_before + [BidRecord(bid.supplier_id, bid.total_price, bid.submitted_at)]

    # --- Step 6: ask the pure service for a decision. ---
    config_vo = AuctionConfigVO(
        trigger_window_minutes=rfq.config.trigger_window_minutes,
        extension_minutes=rfq.config.extension_minutes,
        trigger_type=TriggerType(rfq.config.trigger_type),
    )
    decision = evaluate_extension(
        bids_before=bids_before,
        bids_after=bids_after,
        config=config_vo,
        current_close_at=rfq.current_close_at,
        forced_close_at=rfq.forced_close_at,
        now=now,
    )

    # --- Step 7: apply the decision, if any. ---
    if decision.extended:
        db.add(AuctionEvent(
            rfq_id=rfq.id,
            event_type=EventType.EXTENDED.value,
            bid_id=bid.id,
            old_close_at=rfq.current_close_at,
            new_close_at=decision.new_close_at,
            reason=decision.reason,
            created_at=now,
        ))
        rfq.current_close_at = decision.new_close_at

    # --- Step 8: commit. Lock releases. ---
    db.commit()
    db.refresh(bid)
    return bid


def compute_status(rfq: Rfq, now: datetime | None = None) -> str:
    """
    Status is DERIVED, never stored, so it can never go stale between
    a background job's ticks (see our earlier discussion of 'derive
    state when it's a pure function of time, use a job only for
    side-effects like notifications').
    """
    now = _as_utc(now or datetime.now(timezone.utc))
    if now < _as_utc(rfq.bid_start_at):
        return "SCHEDULED"
    if now >= _as_utc(rfq.forced_close_at):
        return "FORCE_CLOSED"
    if now >= _as_utc(rfq.current_close_at):
        return "CLOSED"
    return "ACTIVE"


def current_lowest_bid(rfq: Rfq) -> float | None:
    if not rfq.bids:
        return None
    ranked_ids = rank_suppliers(_to_bid_records(rfq.bids))
    best_supplier = ranked_ids[0]
    return min(b.total_price for b in rfq.bids if b.supplier_id == best_supplier)

#delete RFQ API kinda sorta developmental use but can be used in production with slight tweaks:
def delete_rfq(db: Session, rfq_id: str) -> None:
    # 1. Lock the RFQ row so no concurrent bid submission is in flight
    rfq = db.execute(
        select(Rfq).where(Rfq.id == rfq_id).with_for_update()
    ).scalar_one_or_none()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")

    # 2. Delete dependent child records first to prevent ForeignKeyViolation
    db.execute(delete(AuctionEvent).where(AuctionEvent.rfq_id == rfq_id))
    db.execute(delete(Bid).where(Bid.rfq_id == rfq_id))
    db.execute(delete(AuctionConfig).where(AuctionConfig.rfq_id == rfq_id))

    # 3. Delete the RFQ itself and commit
    db.delete(rfq)
    db.commit()


# delete bid API, again purely for developmental processes and clean up
def delete_bid(db: Session, rfq_id: str, bid_id: str) -> None:
    # 1. Lock the RFQ row to stay safe against concurrent bid submissions
    rfq = db.execute(
        select(Rfq).where(Rfq.id == rfq_id).with_for_update()
    ).scalar_one_or_none()
    if not rfq:
        raise HTTPException(status_code=404, detail="RFQ not found")

    # 2. Verify the bid exists and belongs to this RFQ
    bid = db.execute(
        select(Bid).where(Bid.id == bid_id, Bid.rfq_id == rfq_id)
    ).scalar_one_or_none()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found for this RFQ")

    # 3. Detach bid_id on existing audit events so Postgres doesn't throw a ForeignKeyViolation
    db.execute(
        update(AuctionEvent)
        .where(AuctionEvent.bid_id == bid_id)
        .values(bid_id=None)
    )

    # 4. Delete the bid and commit
    db.delete(bid)
    db.commit()
