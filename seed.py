"""
Seed script to populate sample British Auction RFQs and initial bids
so you can immediately test the frontend and API.

Run with:
    python seed.py
"""
from datetime import datetime, timedelta, timezone

from app.database import Base, SessionLocal, engine
from app.domain import TriggerType
from app.repositories import rfq_repository as repo
from app.schemas import AuctionConfigCreate, BidCreate, RfqCreate


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        suffix = now.strftime("%H%M%S")

        rfq1 = repo.create_rfq(
            db,
            RfqCreate(
                reference_id=f"RFQ-2026-FCL-{suffix}",
                name="Mumbai (INNSA) to Rotterdam (NLRTM) - 40ft HC Container",
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
        )
        repo.submit_bid(
            db,
            rfq1.id,
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
            now=now - timedelta(minutes=15),
        )
        repo.submit_bid(
            db,
            rfq1.id,
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
            now=now - timedelta(minutes=12),
        )

        rfq2 = repo.create_rfq(
            db,
            RfqCreate(
                reference_id=f"RFQ-2026-AIR-{suffix}",
                name="Delhi (INDEL) to Frankfurt (DEFRA) - Cold Chain Air Freight",
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
        )
        repo.submit_bid(
            db,
            rfq2.id,
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
            now=now - timedelta(minutes=10),
        )

        print(f"Seeded 2 active British Auction RFQs: {rfq1.reference_id}, {rfq2.reference_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
