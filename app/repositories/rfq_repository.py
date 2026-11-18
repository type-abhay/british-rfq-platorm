"""
RfqRepository: transactional database access with row-level locking
and UTC-normalized timestamp comparisons.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.domain import AuctionConfig as AuctionConfigVO
from app.domain import BidRecord, TriggerType
from app.models import AuctionConfig, AuctionEvent, Bid, EventType, Rfq
from app.schemas import BidCreate, RfqCreate
from app.services.extension_service import evaluate as evaluate_extension
from app.services.ranking_service import rank_suppliers


class RfqNotFoundError(Exception):
    pass


class DuplicateReferenceIdError(Exception):
    pass


class BidNotFoundError(Exception):
    pass


class BiddingNotOpenError(Exception):
    pass


def _as_utc(dt: datetime) -> datetime:
    """Guarantees timezone-aware UTC datetime for safe comparisons across SQLite and PostgreSQL."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def create_rfq(db: Session, payload: RfqCreate) -> Rfq:
    rfq = Rfq(
        reference_id=payload.reference_id,
        name=payload.name,
        bid_start_at=_as_utc(payload.bid_start_at),
        bid_close_at=_as_utc(payload.bid_close_at),
        current_close_at=_as_utc(payload.bid_close_at),
        forced_close_at=_as_utc(payload.forced_close_at),
        pickup_date=_as_utc(payload.pickup_date),
    )
    rfq.config = AuctionConfig(
        trigger_window_minutes=payload.config.trigger_window_minutes,
        extension_minutes=payload.config.extension_minutes,
        trigger_type=payload.config.trigger_type.value,
    )
    db.add(rfq)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateReferenceIdError(f"RFQ with reference_id '{payload.reference_id}' already exists.") from exc
    db.refresh(rfq)
    return rfq


def list_rfqs(db: Session) -> list[Rfq]:
    stmt = select(Rfq).options(selectinload(Rfq.bids)).order_by(Rfq.created_at.desc())
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


#delete RFQ API kinda sorta developmental use but can be used in production with slight tweaks:
def delete_rfq(db: Session, rfq_id: str) -> None:
    rfq = db.execute(
        select(Rfq).where(Rfq.id == rfq_id).with_for_update()
    ).scalar_one_or_none()
    if not rfq:
        raise RfqNotFoundError(rfq_id)

    db.execute(delete(AuctionEvent).where(AuctionEvent.rfq_id == rfq_id))
    db.execute(delete(Bid).where(Bid.rfq_id == rfq_id))
    db.execute(delete(AuctionConfig).where(AuctionConfig.rfq_id == rfq_id))
    db.delete(rfq)
    db.commit()



# delete bid API, again purely for developmental processes and clean up
def delete_bid(db: Session, rfq_id: str, bid_id: str) -> None:
    rfq = db.execute(
        select(Rfq).where(Rfq.id == rfq_id).with_for_update()
    ).scalar_one_or_none()
    if not rfq:
        raise RfqNotFoundError(rfq_id)

    bid = db.execute(
        select(Bid).where(Bid.id == bid_id, Bid.rfq_id == rfq_id)
    ).scalar_one_or_none()
    if not bid:
        raise BidNotFoundError(bid_id)

    db.execute(
        update(AuctionEvent)
        .where(AuctionEvent.bid_id == bid_id)
        .values(bid_id=None)
    )
    db.delete(bid)
    db.commit()


def _to_bid_records(bids: list[Bid]) -> list[BidRecord]:
    return [BidRecord(b.supplier_id, b.total_price, _as_utc(b.submitted_at)) for b in bids]


def submit_bid(db: Session, rfq_id: str, payload: BidCreate, now: datetime | None = None) -> Bid:
    """
    Transactional write path with row-level lock (`SELECT ... FOR UPDATE`).
    """
    now = _as_utc(now or datetime.now(timezone.utc))

    stmt = (
        select(Rfq)
        .options(selectinload(Rfq.bids), selectinload(Rfq.config))
        .where(Rfq.id == rfq_id)
        .with_for_update()
    )
    rfq = db.scalars(stmt).first()
    if rfq is None:
        raise RfqNotFoundError(rfq_id)

    bid_start_at = _as_utc(rfq.bid_start_at)
    current_close_at = _as_utc(rfq.current_close_at)
    forced_close_at = _as_utc(rfq.forced_close_at)

    if now < bid_start_at:
        raise BiddingNotOpenError("Bidding has not started yet for this RFQ.")
    if now >= current_close_at or now >= forced_close_at:
        raise BiddingNotOpenError("Bidding is closed for this RFQ.")

    bids_before = _to_bid_records(rfq.bids)

    total_price = round(
        payload.freight_charges + payload.origin_charges + payload.destination_charges, 2
    )
    bid = Bid(
        rfq_id=rfq.id,
        supplier_id=payload.supplier_id.strip(),
        supplier_name=payload.supplier_name.strip(),
        carrier_name=payload.carrier_name.strip(),
        freight_charges=payload.freight_charges,
        origin_charges=payload.origin_charges,
        destination_charges=payload.destination_charges,
        total_price=total_price,
        transit_time_days=payload.transit_time_days,
        quote_validity=payload.quote_validity,
        submitted_at=now,
    )
    db.add(bid)
    db.flush()

    db.add(
        AuctionEvent(
            rfq_id=rfq.id,
            event_type=EventType.BID_SUBMITTED.value,
            bid_id=bid.id,
            reason=(
                f"{bid.supplier_name} ({bid.supplier_id}) submitted a quote of "
                f"${bid.total_price:,.2f} via {bid.carrier_name}."
            ),
            created_at=now,
        )
    )

    bids_after = bids_before + [BidRecord(bid.supplier_id, bid.total_price, _as_utc(bid.submitted_at))]

    config_vo = AuctionConfigVO(
        trigger_window_minutes=rfq.config.trigger_window_minutes,
        extension_minutes=rfq.config.extension_minutes,
        trigger_type=TriggerType(rfq.config.trigger_type),
    )
    decision = evaluate_extension(
        bids_before=bids_before,
        bids_after=bids_after,
        config=config_vo,
        current_close_at=current_close_at,
        forced_close_at=forced_close_at,
        now=now,
    )

    if decision.extended:
        capped_note = (
            " (capped at Forced Bid Close Time)"
            if decision.new_close_at >= forced_close_at
            else ""
        )
        db.add(
            AuctionEvent(
                rfq_id=rfq.id,
                event_type=EventType.EXTENDED.value,
                bid_id=bid.id,
                old_close_at=current_close_at,
                new_close_at=decision.new_close_at,
                reason=f"{decision.reason}{capped_note}",
                created_at=now,
            )
        )
        rfq.current_close_at = decision.new_close_at

    db.commit()
    db.refresh(bid)
    return bid


def compute_status(rfq: Rfq, now: datetime | None = None) -> str:
    now = _as_utc(now or datetime.now(timezone.utc))
    bid_start_at = _as_utc(rfq.bid_start_at)
    current_close_at = _as_utc(rfq.current_close_at)
    forced_close_at = _as_utc(rfq.forced_close_at)

    if now < bid_start_at:
        return "SCHEDULED"
    if now >= forced_close_at:
        return "FORCE_CLOSED"
    if now >= current_close_at:
        return "CLOSED"
    return "ACTIVE"


def current_lowest_bid(rfq: Rfq) -> float | None:
    if not rfq.bids:
        return None
    ranked_ids = rank_suppliers(_to_bid_records(rfq.bids))
    best_supplier = ranked_ids[0]
    return min(b.total_price for b in rfq.bids if b.supplier_id == best_supplier)
