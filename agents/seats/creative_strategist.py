from pathlib import Path

from agents.base_seat import BaseSeat, SeatResult
from ._common import prompt_path


class CreativeStrategist(BaseSeat):
    def __init__(self, prompts_dir: Path | None = None, **kwargs):
        super().__init__("creative_strategist", prompts_dir or prompt_path("creative_strategist", "system.md").parent, **kwargs)

    def mining_pass(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_mining_pass.md").read_text(), evidence)

    def persona_cards(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_persona_cards.md").read_text(), evidence)

    def angle_bank(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_angle_bank.md").read_text(), evidence)