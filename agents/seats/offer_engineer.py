"""Offer Engineer — rebuilds price/bundle/bonus/guarantee when the offer is the constraint.

GAP-FILL: the client's docs give this seat no prompt; see agents/prompts/offer_engineer.
Proposals only; never changes a live price.
"""

from agents.base_seat import BaseSeat, SeatResult


class OfferEngineer(BaseSeat):
    def __init__(self, **kwargs):
        super().__init__("offer_engineer", **kwargs)

    def rebuild(self, evidence: dict) -> SeatResult:
        return self.run_task("task_offer_rebuild_gap_fill.md", evidence)
