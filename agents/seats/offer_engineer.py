from pathlib import Path

from agents.base_seat import BaseSeat, SeatResult
from ._common import prompt_path


class OfferEngineer(BaseSeat):
    """Gap-filled wrapper; source prompt explicitly labels this seat unsourced."""

    def __init__(self, prompts_dir: Path | None = None, **kwargs):
        super().__init__("offer_engineer", prompts_dir or prompt_path("offer_engineer", "system.md").parent, **kwargs)

    def offer_rebuild(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_offer_rebuild_gap_fill.md").read_text(), evidence)