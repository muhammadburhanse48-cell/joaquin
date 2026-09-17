"""Small helpers shared by thin seat wrappers."""

from pathlib import Path

from agents.base_seat import BaseSeat, SeatResult

PROMPTS_ROOT = Path(__file__).resolve().parents[1] / "prompts"


def prompt_path(seat: str, task: str) -> Path:
    return PROMPTS_ROOT / seat / task


def run_task(seat: BaseSeat, task: str, evidence: dict, **kwargs) -> SeatResult:
    return seat.run(prompt_path(seat.seat_name, task).read_text(), evidence, **kwargs)