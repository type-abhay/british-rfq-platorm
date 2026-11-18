"""
Tests for ExtensionService.evaluate().

The first few tests deliberately reproduce the exact numbers from the
assignment PDF (section 6) so that passing them is direct evidence the
implementation matches spec, not just "a reasonable interpretation."
"""
from datetime import datetime, timedelta

from app.domain import AuctionConfig, BidRecord, TriggerType
from app.services.extension_service import evaluate

CLOSE = datetime(2026, 1, 1, 18, 0, 0)  # 6:00 PM, matches the spec's example


def at(time_str: str) -> datetime:
    """Builds a datetime on the same day as CLOSE, e.g. at('5:55 PM')."""
    t = datetime.strptime(time_str, "%I:%M %p")
    return CLOSE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)


def bid(supplier_id: str, price: float, time_str: str) -> BidRecord:
    return BidRecord(supplier_id, price, at(time_str))


# ---------------------------------------------------------------- #
# 6.3(a) BID_RECEIVED — spec example: window=10min, bid at 5:55 PM  #
# ---------------------------------------------------------------- #

def test_bid_received_inside_window_extends_by_Y():
    config = AuctionConfig(trigger_window_minutes=10, extension_minutes=5, trigger_type=TriggerType.BID_RECEIVED)
    bids_before = [bid("supplier_a", 1000, "5:40 PM")]
    bids_after = bids_before + [bid("supplier_b", 950, "5:55 PM")]

    decision = evaluate(
        bids_before=bids_before,
        bids_after=bids_after,
        config=config,
        current_close_at=CLOSE,
        forced_close_at=CLOSE + timedelta(hours=1),
        now=at("5:55 PM"),
    )

    assert decision.extended is True
    assert decision.new_close_at == at("6:05 PM")  # 6:00 -> 6:05, per spec example


def test_bid_received_outside_window_does_not_extend():
    config = AuctionConfig(trigger_window_minutes=10, extension_minutes=5, trigger_type=TriggerType.BID_RECEIVED)
    bids_before = [bid("supplier_a", 1000, "5:00 PM")]
    bids_after = bids_before + [bid("supplier_b", 950, "5:30 PM")]  # 30 min before close, outside 10-min window

    decision = evaluate(
        bids_before=bids_before,
        bids_after=bids_after,
        config=config,
        current_close_at=CLOSE,
        forced_close_at=CLOSE + timedelta(hours=1),
        now=at("5:30 PM"),
    )

    assert decision.extended is False
    assert decision.new_close_at == CLOSE


def test_window_boundary_is_inclusive():
    # Exactly 10 minutes before close == exactly at the window edge.
    # Treated as INSIDE the window (>=), matching "between 5:50-6:00 PM".
    config = AuctionConfig(trigger_window_minutes=10, extension_minutes=5, trigger_type=TriggerType.BID_RECEIVED)
    bids_before: list[BidRecord] = []
    bids_after = [bid("supplier_a", 1000, "5:50 PM")]

    decision = evaluate(
        bids_before=bids_before,
        bids_after=bids_after,
        config=config,
        current_close_at=CLOSE,
        forced_close_at=CLOSE + timedelta(hours=1),
        now=at("5:50 PM"),
    )

    assert decision.extended is True


# ---------------------------------------------------------------- #
# 6.3(b) ANY_RANK_CHANGE — spec example: Supplier B underbids A     #
# ---------------------------------------------------------------- #

def test_any_rank_change_triggers_when_order_shuffles():
    config = AuctionConfig(trigger_window_minutes=10, extension_minutes=5, trigger_type=TriggerType.ANY_RANK_CHANGE)
    bids_before = [bid("supplier_a", 900, "5:40 PM"), bid("supplier_b", 950, "5:45 PM")]
    # B underbids A at 5:58 PM -> order flips
    bids_after = bids_before + [bid("supplier_b", 850, "5:58 PM")]

    decision = evaluate(
        bids_before=bids_before,
        bids_after=bids_after,
        config=config,
        current_close_at=CLOSE,
        forced_close_at=CLOSE + timedelta(hours=1),
        now=at("5:58 PM"),
    )

    assert decision.extended is True


def test_any_rank_change_does_not_trigger_when_order_unchanged():
    config = AuctionConfig(trigger_window_minutes=10, extension_minutes=5, trigger_type=TriggerType.ANY_RANK_CHANGE)
    bids_before = [bid("supplier_a", 900, "5:40 PM"), bid("supplier_b", 950, "5:45 PM")]
    # B bids again but still above A -> no order change
    bids_after = bids_before + [bid("supplier_b", 920, "5:58 PM")]

    decision = evaluate(
        bids_before=bids_before,
        bids_after=bids_after,
        config=config,
        current_close_at=CLOSE,
        forced_close_at=CLOSE + timedelta(hours=1),
        now=at("5:58 PM"),
    )

    assert decision.extended is False


# ---------------------------------------------------------------- #
# 6.3(c) L1_CHANGE — spec example: Supplier C becomes new L1        #
# ---------------------------------------------------------------- #

def test_l1_change_triggers_only_when_the_leader_changes():
    config = AuctionConfig(trigger_window_minutes=10, extension_minutes=5, trigger_type=TriggerType.L1_CHANGE)
    bids_before = [
        bid("supplier_a", 900, "5:40 PM"),   # L1
        bid("supplier_b", 950, "5:45 PM"),   # L2
        bid("supplier_c", 970, "5:50 PM"),   # L3
    ]
    # C undercuts everyone at 5:59 PM -> becomes new L1
    bids_after = bids_before + [bid("supplier_c", 850, "5:59 PM")]

    decision = evaluate(
        bids_before=bids_before,
        bids_after=bids_after,
        config=config,
        current_close_at=CLOSE,
        forced_close_at=CLOSE + timedelta(hours=1),
        now=at("5:59 PM"),
    )

    assert decision.extended is True
    assert "supplier_c" in decision.reason


def test_l1_change_does_not_trigger_on_lower_rank_shuffle():
    # L2 and L3 swap, but L1 (supplier_a) is untouched -> no extension
    # under the L1_CHANGE policy, even though ANY_RANK_CHANGE would fire.
    config = AuctionConfig(trigger_window_minutes=10, extension_minutes=5, trigger_type=TriggerType.L1_CHANGE)
    bids_before = [
        bid("supplier_a", 900, "5:40 PM"),   # L1, stays L1
        bid("supplier_b", 950, "5:45 PM"),   # L2
        bid("supplier_c", 970, "5:50 PM"),   # L3
    ]
    bids_after = bids_before + [bid("supplier_c", 940, "5:59 PM")]  # C passes B, but not A

    decision = evaluate(
        bids_before=bids_before,
        bids_after=bids_after,
        config=config,
        current_close_at=CLOSE,
        forced_close_at=CLOSE + timedelta(hours=1),
        now=at("5:59 PM"),
    )

    assert decision.extended is False


# ---------------------------------------------------------------- #
# Section 7 — forced close ceiling must never be exceeded           #
# ---------------------------------------------------------------- #

def test_extension_is_capped_at_forced_close():
    # Extension of 30 min would normally push to 6:30 PM, but forced
    # close is 6:10 PM -> must cap there, not exceed it.
    config = AuctionConfig(trigger_window_minutes=10, extension_minutes=30, trigger_type=TriggerType.BID_RECEIVED)
    bids_after = [bid("supplier_a", 1000, "5:55 PM")]

    decision = evaluate(
        bids_before=[],
        bids_after=bids_after,
        config=config,
        current_close_at=CLOSE,                       # 6:00 PM
        forced_close_at=at("6:10 PM"),
        now=at("5:55 PM"),
    )

    assert decision.extended is True
    assert decision.new_close_at == at("6:10 PM")  # capped, not 6:30 PM


def test_no_further_extension_once_already_at_forced_close():
    config = AuctionConfig(trigger_window_minutes=10, extension_minutes=5, trigger_type=TriggerType.BID_RECEIVED)
    bids_after = [bid("supplier_a", 1000, "5:55 PM")]

    decision = evaluate(
        bids_before=[],
        bids_after=bids_after,
        config=config,
        current_close_at=at("6:10 PM"),   # already sitting at the ceiling
        forced_close_at=at("6:10 PM"),
        now=at("6:05 PM"),
    )

    assert decision.extended is False
    assert decision.new_close_at == at("6:10 PM")
