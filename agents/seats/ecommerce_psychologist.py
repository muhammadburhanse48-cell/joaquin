from pathlib import Path

from agents.base_seat import BaseSeat, SeatResult, assert_isolated_evidence
from ._common import prompt_path


class EcommercePsychologist(BaseSeat):
    def __init__(self, prompts_dir: Path | None = None, **kwargs):
        super().__init__("ecommerce_psychologist", prompts_dir or prompt_path("ecommerce_psychologist", "system.md").parent, **kwargs)

    def psych_review(self, evidence: dict) -> SeatResult:
        assert_isolated_evidence(evidence)
        return self.run(prompt_path(self.seat_name, "task_psych_review.md").read_text(), evidence)