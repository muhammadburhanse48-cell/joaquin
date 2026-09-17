from pathlib import Path

from agents.base_seat import BaseSeat, SeatResult
from ._common import prompt_path


class Analyst(BaseSeat):
    def __init__(self, prompts_dir: Path | None = None, **kwargs):
        super().__init__("analyst", prompts_dir or prompt_path("analyst", "system.md").parent, **kwargs)

    def readout(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_readout.md").read_text(), evidence)