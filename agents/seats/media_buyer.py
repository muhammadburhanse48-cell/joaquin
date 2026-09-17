from pathlib import Path

from agents.base_seat import BaseSeat, SeatResult
from ._common import prompt_path


class MediaBuyer(BaseSeat):
    def __init__(self, prompts_dir: Path | None = None, **kwargs):
        super().__init__("media_buyer", prompts_dir or prompt_path("media_buyer", "system.md").parent, **kwargs)

    def scaling_proposal(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_scaling_proposal.md").read_text(), evidence)