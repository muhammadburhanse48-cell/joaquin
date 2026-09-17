from pathlib import Path

from agents.base_seat import BaseSeat, SeatResult
from ._common import prompt_path


class OpportunityScout(BaseSeat):
    def __init__(self, prompts_dir: Path | None = None, **kwargs):
        super().__init__("opportunity_scout", prompts_dir or prompt_path("opportunity_scout", "system.md").parent, **kwargs)

    def visual_teardown(self, evidence: dict, **kwargs) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_visual_teardown.md").read_text(), evidence, **kwargs)

    def pattern_mining(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_pattern_mining.md").read_text(), evidence)

    def swipe_vault(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_swipe_vault.md").read_text(), evidence)

    def video_teardown(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_video_teardown.md").read_text(), evidence)