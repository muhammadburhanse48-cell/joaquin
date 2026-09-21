"""Creative Director, Mode B — judge panel and QA (isolated critic).

Refuses, in code, to review anything while holding the brief that produced it.
"""

from agents.base_seat import BaseSeat, SeatResult


class CreativeDirectorB(BaseSeat):
    critic = True
    max_tokens = 12000

    def __init__(self, **kwargs):
        super().__init__("creative_director_b", **kwargs)

    def judge_and_qa(self, evidence: dict, images: list) -> SeatResult:
        """images: labelled (label, bytes) — candidates, the product photo, the exemplar."""
        if not images:
            raise ValueError("the judge panel reviews images; none attached")
        return self.run_task("task_judge_qa.md", evidence, attached_images=images)

    def batch_sweep(self, evidence: dict, images: list) -> SeatResult:
        if not images:
            raise ValueError("the batch sweep reviews the shipping images; none attached")
        return self.run_task("task_batch_sweep.md", evidence, attached_images=images)
