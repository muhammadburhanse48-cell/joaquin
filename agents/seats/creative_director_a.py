from pathlib import Path

from agents.base_seat import BaseSeat, SeatResult
from ._common import prompt_path


class CreativeDirectorA(BaseSeat):
    def __init__(self, prompts_dir: Path | None = None, **kwargs):
        super().__init__("creative_director_a", prompts_dir or prompt_path("creative_director_a", "system.md").parent, **kwargs)

    def concept_portfolio(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_concept_portfolio.md").read_text(), evidence)