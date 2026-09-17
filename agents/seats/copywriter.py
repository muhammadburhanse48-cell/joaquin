from pathlib import Path

from agents.base_seat import BaseSeat, SeatResult
from ._common import prompt_path


class Copywriter(BaseSeat):
    def __init__(self, prompts_dir: Path | None = None, **kwargs):
        super().__init__("copywriter", prompts_dir or prompt_path("copywriter", "system.md").parent, **kwargs)

    def ad(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_ad.md").read_text(), evidence)

    def advertorial(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_advertorial.md").read_text(), evidence)

    def pdp(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_pdp.md").read_text(), evidence)

    def email(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_email.md").read_text(), evidence)