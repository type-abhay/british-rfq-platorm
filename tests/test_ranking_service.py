"""
Tests for RankingService.

Every test constructs plain BidRecord objects — no database, no FastAPI
app, no fixtures beyond a helper for building timestamps. This is the
payoff of keeping the service pure: these tests run in milliseconds.
"""
from datetime import datetime, timedelta

from app.domain import BidRecord
from app.services.ranking_service import rank_suppliers

T0 = datetime(2026, 1, 1, 17, 0, 0)  # arbitrary fixed "5:00 PM" anchor


def at(minutes_after_t0: float) -> datetime:
    return T0 + timedelta(minutes=minutes_after_t0)


def test_single_bid_is_rank_one():
    bids = [BidRecord("supplier_a", 1000.0, at(0))]
    assert rank_suppliers(bids) == ["supplier_a"]


def test_lower_price_ranks_higher():
    bids = [
        BidRecord("supplier_a", 1000.0, at(0)),
        BidRecord("supplier_b", 900.0, at(1)),
    ]
    assert rank_suppliers(bids) == ["supplier_b", "supplier_a"]


def test_supplier_standing_is_their_best_bid_not_latest():
    # Supplier A bids low, then (for whatever reason) submits a HIGHER
    # bid later. Their standing should stay at their best price, 900 —
    # not regress to the later, worse number.
    bids = [
        BidRecord("supplier_a", 900.0, at(0)),
        BidRecord("supplier_a", 950.0, at(5)),
        BidRecord("supplier_b", 920.0, at(6)),
    ]
    assert rank_suppliers(bids) == ["supplier_a", "supplier_b"]


def test_tie_is_broken_by_earlier_timestamp():
    bids = [
        BidRecord("supplier_a", 1000.0, at(0)),
        BidRecord("supplier_b", 1000.0, at(1)),
    ]
    # A reached the price first, so A outranks B despite an exact tie.
    assert rank_suppliers(bids) == ["supplier_a", "supplier_b"]


def test_three_way_ranking_is_fully_ordered():
    bids = [
        BidRecord("supplier_a", 1000.0, at(0)),
        BidRecord("supplier_b", 900.0, at(1)),
        BidRecord("supplier_c", 950.0, at(2)),
    ]
    assert rank_suppliers(bids) == ["supplier_b", "supplier_c", "supplier_a"]


def test_empty_bid_list_returns_empty_ranking():
    assert rank_suppliers([]) == []
