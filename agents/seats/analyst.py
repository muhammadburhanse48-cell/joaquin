"""Analyst — the readout. Verdicts need numbers and a spend floor (enforced by the loop)."""

from agents.base_seat import BaseSeat, SeatResult


class Analyst(BaseSeat):
    max_tokens = 16000

    def __init__(self, **kwargs):
        super().__init__("analyst", **kwargs)

    def readout(self, evidence: dict) -> SeatResult:
        return self.run_task("task_readout.md", evidence)
