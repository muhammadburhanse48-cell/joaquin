"""Ecommerce Psychologist — one pre-spend pass over the concept portfolio (critic)."""

from agents.base_seat import BaseSeat, SeatResult


class EcommercePsychologist(BaseSeat):
    critic = True

    def __init__(self, **kwargs):
        super().__init__("ecommerce_psychologist", **kwargs)

    def psych_review(self, evidence: dict) -> SeatResult:
        return self.run_task("task_psych_review.md", evidence)
