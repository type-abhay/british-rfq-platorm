"""
RankingService: turns a flat list of bids into a supplier ranking.

The spec says "supplier ranking (L1, L2, L3...)" and "lowest bidder (L1)
rank change" — but a supplier submits MANY bids over time. Before we can
ask "did the ranking change", we have to answer a question the spec
doesn't spell out: what counts as a supplier's current standing?

Decision made here: each supplier's standing is their LOWEST price seen
so far (their best offer), not their most recent bid. This matches how
real reverse auctions work — a supplier doesn't need to re-bid to stay
ranked; their best offer stands until undercut.

Tie-break rule: if two suppliers have the same lowest price, the one
who reached that price FIRST ranks higher. This rewards being first to
commit to a price rather than copying a competitor's number, and it
means a tying bid never itself causes a rank change (since it doesn't
unseat the earlier supplier).
"""
from __future__ import annotations

from app.domain import BidRecord


def rank_suppliers(bids: list[BidRecord]) -> list[str]:
    """
    Returns supplier_ids ordered best-to-worst (index 0 == L1).

    Each supplier's best (lowest) bid is used as their standing.
    Ties are broken by whichever supplier reached that price first.
    """
    best_per_supplier: dict[str, BidRecord] = {}

    for bid in bids:
        current_best = best_per_supplier.get(bid.supplier_id)
        if current_best is None or bid.total_price < current_best.total_price:
            best_per_supplier[bid.supplier_id] = bid
        elif bid.total_price == current_best.total_price and bid.submitted_at < current_best.submitted_at:
            # Shouldn't normally happen (bids arrive in time order) but
            # keeps the function correct even if called with reordered data.
            best_per_supplier[bid.supplier_id] = bid

    ordered = sorted(
        best_per_supplier.values(),
        key=lambda b: (b.total_price, b.submitted_at),
    )
    return [b.supplier_id for b in ordered]
