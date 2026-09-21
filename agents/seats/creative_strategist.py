"""Creative Strategist — mines voice-of-customer, builds persona cards and the angle bank."""

from agents.base_seat import BaseSeat, SeatResult


class CreativeStrategist(BaseSeat):
    max_tokens = 16000

    def __init__(self, **kwargs):
        super().__init__("creative_strategist", **kwargs)

    def mining_pass(self, evidence: dict) -> SeatResult:
        return self.run_task("task_mining_pass.md", evidence)

    def persona_cards(self, evidence: dict) -> SeatResult:
        return self.run_task("task_persona_cards.md", evidence)

    def angle_bank(self, evidence: dict) -> SeatResult:
        return self.run_task("task_angle_bank.md", evidence)
