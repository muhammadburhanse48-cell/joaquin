"""Creative Director, Mode A (author) — concept portfolio and briefs.

Never writes a generation prompt for an image it will later judge; that is the
Graphic Designer's job and Mode B's judgement.
"""

from agents.base_seat import BaseSeat, SeatResult


class CreativeDirectorA(BaseSeat):
    max_tokens = 12000

    def __init__(self, **kwargs):
        super().__init__("creative_director_a", **kwargs)

    def concept_portfolio(self, evidence: dict) -> SeatResult:
        return self.run_task("task_concept_portfolio.md", evidence)

    def write_briefs(self, evidence: dict) -> SeatResult:
        return self.run_task("task_write_briefs.md", evidence)

    def revise_briefs(self, evidence: dict) -> SeatResult:
        return self.run_task("task_revise_briefs.md", evidence)
