"""Opportunity Scout — visual teardown, pattern mining, swipe vault, video teardown."""

from agents.base_seat import BaseSeat, SeatResult


class OpportunityScout(BaseSeat):
    max_tokens = 12000

    def __init__(self, **kwargs):
        super().__init__("opportunity_scout", **kwargs)

    def visual_teardown(self, evidence: dict, images: list) -> SeatResult:
        """6-8 ad images per call; every image must get a row."""
        if not images:
            raise ValueError("visual teardown reads images, not metadata: none attached")
        return self.run_task("task_visual_teardown.md", evidence, attached_images=images)

    def pattern_mining(self, evidence: dict) -> SeatResult:
        return self.run_task("task_pattern_mining.md", evidence)

    def swipe_vault(self, evidence: dict) -> SeatResult:
        return self.run_task("task_swipe_vault.md", evidence)

    def video_teardown(self, evidence: dict, images: list) -> SeatResult:
        if not images:
            raise ValueError("video teardown reads keyframes: none attached")
        return self.run_task("task_video_teardown.md", evidence, attached_images=images)
