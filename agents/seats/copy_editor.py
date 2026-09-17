from pathlib import Path

from agents.base_seat import BaseSeat, SeatResult
from ._common import prompt_path


class CopyEditor(BaseSeat):
    def __init__(self, prompts_dir: Path | None = None, **kwargs):
        super().__init__("copy_editor", prompts_dir or prompt_path("copy_editor", "system.md").parent, **kwargs)

    def edit(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_edit.md").read_text(), evidence)