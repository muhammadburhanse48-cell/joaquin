"""Video Editor — scripts and motion prompts — plus its separate, isolated script gate."""

from agents.base_seat import BaseSeat, SeatResult


class VideoEditor(BaseSeat):
    max_tokens = 16000

    def __init__(self, **kwargs):
        super().__init__("video_editor", **kwargs)

    def scripts(self, evidence: dict) -> SeatResult:
        return self.run_task("task_scripts.md", evidence)

    def motion(self, evidence: dict, winning_static: bytes) -> SeatResult:
        """Motion is only ever written for a shipped winner with a result behind it."""
        if not winning_static:
            raise ValueError("motion needs the winning static image")
        for key in ("result", "winning_variable"):
            if not str(evidence.get(key, "")).strip():
                raise ValueError(
                    f"refusing to animate without {key!r}: the creative must have already won"
                )
        return self.run_task("task_motion.md", evidence, attached_images=[winning_static])


class VideoScriptGate(BaseSeat):
    """The client requires the script gate to be a fresh, isolated critic call."""

    critic = True

    def __init__(self, **kwargs):
        super().__init__(
            "video_editor", system_file="system_script_gate.md", **kwargs
        )

    def review(self, evidence: dict) -> SeatResult:
        return self.run_task("task_script_gate.md", evidence)
