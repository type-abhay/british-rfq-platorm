"""
ExtensionService: decides whether a new bid should push the auction's
close time back, and by how much.

This function is intentionally a pure calculation:
    (ranking before, ranking after, config, the clock) -> a decision

It takes no database session and performs no I/O. The caller (a
repository/route, inside a locked transaction) is responsible for
gathering the "before" and "after" bid snapshots and for persisting
the decision. That separation is what makes this testable without
spinning up Postgres, and it's also what makes the locking story in
the repository layer easy to reason about: by the time this function
runs, all the data it needs has already been read under the lock.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.domain import AuctionConfig, BidRecord, ExtensionDecision, TriggerType
from app.services.ranking_service import rank_suppliers


def evaluate(
    *,
    bids_before: list[BidRecord],
    bids_after: list[BidRecord],
    config: AuctionConfig,
    current_close_at: datetime,
    forced_close_at: datetime,
    now: datetime,
) -> ExtensionDecision:
    """
    bids_before / bids_after: the full bid list for this RFQ, taken
        immediately before and immediately after inserting the new bid.
        Passing both (rather than just "after") is what lets us detect
        a RANK CHANGE, not just a bid's existence.
    config: X (trigger_window_minutes), Y (extension_minutes), trigger_type.
    current_close_at: the auction's live deadline (moves with extensions).
    forced_close_at: the hard ceiling (never moves).
    now: the moment the triggering bid was recorded. Passed in explicitly
        (never read from datetime.now() inside this function) so the
        function stays deterministic and trivially testable.
    """
    no_extension = ExtensionDecision(extended=False, new_close_at=current_close_at, reason=None)

    # --- Rule from spec section 6.1: only bids inside the trigger
    # window can cause an extension at all. A bid early in the auction
    # is just normal competition, not last-second sniping. ---
    window_start = current_close_at - timedelta(minutes=config.trigger_window_minutes)
    if now < window_start:
        return no_extension

    # --- Rule from spec section 7: never extend past the forced close.
    # If we're already AT the forced close, there is nothing left to
    # extend, regardless of what triggered. ---
    if current_close_at >= forced_close_at:
        return no_extension

    ranks_before = rank_suppliers(bids_before)
    ranks_after = rank_suppliers(bids_after)

    triggered, reason = _check_trigger(config.trigger_type, ranks_before, ranks_after, now)
    if not triggered:
        return no_extension

    candidate_close = current_close_at + timedelta(minutes=config.extension_minutes)
    new_close_at = min(candidate_close, forced_close_at)

    # If the cap already equals the current close (we were already
    # sitting exactly at the ceiling), there's effectively no extension
    # to grant even though a trigger fired.
    if new_close_at <= current_close_at:
        return no_extension

    return ExtensionDecision(extended=True, new_close_at=new_close_at, reason=reason)


def _check_trigger(
    trigger_type: TriggerType,
    ranks_before: list[str],
    ranks_after: list[str],
    now: datetime,
) -> tuple[bool, str | None]:
    """Returns (triggered, human-readable reason) for one trigger policy."""

    if trigger_type == TriggerType.BID_RECEIVED:
        # By the time evaluate() is called, a bid has already been
        # recorded within the window (that's what prompted the call),
        # so this trigger always fires once we're past the window check.
        return True, f"New bid received at {now:%I:%M %p} within the trigger window."

    if trigger_type == TriggerType.ANY_RANK_CHANGE:
        if ranks_before != ranks_after:
            return True, f"Supplier ranking changed at {now:%I:%M %p} ({ranks_before} -> {ranks_after})."
        return False, None

    if trigger_type == TriggerType.L1_CHANGE:
        l1_before = ranks_before[0] if ranks_before else None
        l1_after = ranks_after[0] if ranks_after else None
        if l1_before != l1_after:
            return True, f"Lowest bidder (L1) changed from {l1_before} to {l1_after} at {now:%I:%M %p}."
        return False, None

    # Defensive: TriggerType is a closed enum, but fail loudly rather
    # than silently granting/denying an extension if it ever grows.
    raise ValueError(f"Unhandled trigger type: {trigger_type}")
