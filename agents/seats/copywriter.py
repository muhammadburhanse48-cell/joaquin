"""Copywriter — ad copy, advertorials, PDP, email. Never invents a quote or statistic."""

from agents.base_seat import BaseSeat, SeatResult


class Copywriter(BaseSeat):
    max_tokens = 16000

    def __init__(self, **kwargs):
        super().__init__("copywriter", **kwargs)

    def ad(self, evidence: dict) -> SeatResult:
        return self.run_task("task_ad.md", evidence)

    def ad_revision(self, evidence: dict) -> SeatResult:
        """The single bounce round from the Copy Editor."""
        return self.run_task("task_ad_revision.md", evidence)

    def advertorial(self, evidence: dict) -> SeatResult:
        return self.run_task("task_advertorial.md", evidence)

    def pdp(self, evidence: dict) -> SeatResult:
        return self.run_task("task_pdp.md", evidence)

    def email(self, evidence: dict) -> SeatResult:
        return self.run_task("task_email.md", evidence)
