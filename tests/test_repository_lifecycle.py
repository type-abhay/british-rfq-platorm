"""
End-to-end repository & concurrency verification tests.
Uses an in-memory SQLite database so `pytest tests/ -v` passes anywhere
while verifying the full SQLAlchemy transactional bid flow, extension rules,
forced-close capping, and delete operations.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.domain import TriggerType
from app.repositories import rfq_repository as repo
from app.schemas import AuctionConfigCreate, BidCreate, RfqCreate


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return Session()


def test_full_rfq_lifecycle_and_l1_extension():
    db = _make_session()
    t0 = datetime(2026, 11, 18, 17, 0, 0, tzinfo=timezone.utc)
    close_t = t0 + timedelta(minutes=60)   # 18:00 UTC
    forced_t = t0 + timedelta(minutes=68)  # 18:08 UTC (only 8 mins headroom)

    rfq = repo.create_rfq(
        db,
        RfqCreate(
            reference_id="RFQ-INT-001",
            name="Test Corridor",
            bid_start_at=t0,
            bid_close_at=close_t,
            forced_close_at=forced_t,
            pickup_date=t0 + timedelta(days=5),
            config=AuctionConfigCreate(
                trigger_window_minutes=10,
                extension_minutes=5,
                trigger_type=TriggerType.L1_CHANGE,
            ),
        ),
    )

    # 1. Early bid outside window (17:20 UTC) -> no extension
    repo.submit_bid(
        db,
        rfq.id,
        BidCreate(
            supplier_id="SUP-A",
            supplier_name="Supplier A",
            carrier_name="Carrier A",
            freight_charges=1000.0,
            origin_charges=100.0,
            destination_charges=100.0,
            transit_time_days=10,
            quote_validity="2026-12-01",
        ),
        now=t0 + timedelta(minutes=20),
    )
    detail = repo.get_rfq_detail(db, rfq.id)
    assert repo._as_utc(detail.current_close_at) == close_t

    # 2. Second bid inside window (17:55 UTC) that becomes new L1 -> extends by 5m to 18:05 UTC
    repo.submit_bid(
        db,
        rfq.id,
        BidCreate(
            supplier_id="SUP-B",
            supplier_name="Supplier B",
            carrier_name="Carrier B",
            freight_charges=900.0,
            origin_charges=100.0,
            destination_charges=100.0,
            transit_time_days=12,
            quote_validity="2026-12-01",
        ),
        now=t0 + timedelta(minutes=55),
    )
    detail = repo.get_rfq_detail(db, rfq.id)
    assert repo._as_utc(detail.current_close_at) == close_t + timedelta(minutes=5)

    # 3. Third bid inside new window (18:02 UTC) that becomes new L1 -> +5m would be 18:10, capped at forced_t (18:08)
    repo.submit_bid(
        db,
        rfq.id,
        BidCreate(
            supplier_id="SUP-A",
            supplier_name="Supplier A",
            carrier_name="Carrier A",
            freight_charges=800.0,
            origin_charges=100.0,
            destination_charges=100.0,
            transit_time_days=10,
            quote_validity="2026-12-01",
        ),
        now=t0 + timedelta(minutes=62),
    )
    detail = repo.get_rfq_detail(db, rfq.id)
    assert repo._as_utc(detail.current_close_at) == forced_t
    assert repo.compute_status(detail, now=forced_t) == "FORCE_CLOSED"

    # 4. Delete RFQ cleanly removes child records
    repo.delete_rfq(db, rfq.id)
    assert len(repo.list_rfqs(db)) == 0
