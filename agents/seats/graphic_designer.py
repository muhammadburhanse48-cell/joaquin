from pathlib import Path

from agents.base_seat import BaseSeat, SeatResult
from ._common import prompt_path


class GraphicDesigner(BaseSeat):
    def __init__(self, prompts_dir: Path | None = None, **kwargs):
        super().__init__("graphic_designer", prompts_dir or prompt_path("graphic_designer", "system.md").parent, **kwargs)

    def generation_template(self, evidence: dict, **kwargs) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_generation_template.md").read_text(), evidence, **kwargs)