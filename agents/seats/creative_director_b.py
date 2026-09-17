from pathlib import Path

from agents.base_seat import BaseSeat, SeatResult, assert_isolated_evidence
from ._common import prompt_path


class CreativeDirectorB(BaseSeat):
    def __init__(self, prompts_dir: Path | None = None, **kwargs):
        super().__init__("creative_director_b", prompts_dir or prompt_path("creative_director_b", "system.md").parent, **kwargs)

    def judge_and_qa(self, evidence: dict, **kwargs) -> SeatResult:
        assert_isolated_evidence(evidence)
        return self.run(prompt_path(self.seat_name, "task_judge_qa.md").read_text(), evidence, **kwargs)

    def batch_sweep(self, evidence: dict) -> SeatResult:
        assert_isolated_evidence(evidence)
        return self.run(prompt_path(self.seat_name, "task_judge_qa.md").read_text(), evidence)