from pathlib import Path

from agents.base_seat import BaseSeat, SeatResult
from ._common import prompt_path


class VideoEditor(BaseSeat):
    def __init__(self, prompts_dir: Path | None = None, **kwargs):
        super().__init__("video_editor", prompts_dir or prompt_path("video_editor", "system.md").parent, **kwargs)

    def scripts(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_scripts.md").read_text(), evidence)

    def motion(self, evidence: dict) -> SeatResult:
        return self.run(prompt_path(self.seat_name, "task_motion.md").read_text(), evidence)