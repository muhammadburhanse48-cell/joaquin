"""Copy Editor — mechanical fixes, one bounce round, 7-lever score (critic).

Receives the draft only, never the copywriter's rationale.
"""

from agents.base_seat import BaseSeat, SeatResult


class CopyEditor(BaseSeat):
    critic = True
    max_tokens = 16000

    def __init__(self, **kwargs):
        super().__init__("copy_editor", **kwargs)

    def edit(self, evidence: dict) -> SeatResult:
        return self.run_task("task_edit.md", evidence)
