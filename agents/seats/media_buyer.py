"""Media Buyer — launch plans and scaling proposals. PROPOSALS ONLY: no code path here
(or anywhere in this repo) touches a live ad account."""

from agents.base_seat import BaseSeat, SeatResult


class MediaBuyer(BaseSeat):
    max_tokens = 12000

    def __init__(self, **kwargs):
        super().__init__("media_buyer", **kwargs)

    def scaling_proposal(self, evidence: dict) -> SeatResult:
        return self.run_task("task_scaling_proposal.md", evidence)

    def launch_plan(self, evidence: dict) -> SeatResult:
        return self.run_task("task_launch_plan.md", evidence)
