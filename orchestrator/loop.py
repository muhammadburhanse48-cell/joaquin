"""The ten-stage creative pipeline."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from agents.base_seat import assert_isolated_evidence
from agents.seats.creative_director_a import CreativeDirectorA
from agents.seats.creative_strategist import CreativeStrategist
from agents.seats.ecommerce_psychologist import EcommercePsychologist
from .brand_state import initialize_brand
from .gates import preflight, render_plan

STAGES = [
    "preflight", "research", "pattern_mining", "concept_portfolio", "psych_review",
    "production", "judge_and_qa", "copy", "launch_plan", "readout",
]


@dataclass
class RunStatus:
    brand: str
    current_stage: str = "idle"
    completed: list[str] = field(default_factory=list)
    error: str | None = None


class Pipeline:
    def __init__(self, root: Path, *, model: str = "claude-sonnet-4-6", client=None):
        self.root = Path(root)
        self.model = model
        self.client = client
        self.statuses: dict[str, RunStatus] = {}

    def get_status(self, brand: str) -> RunStatus:
        return self.statuses.setdefault(brand, RunStatus(brand))

    def preflight_plan(self, brand: str, niche: str) -> str:
        brand_dir = initialize_brand(self.root, brand)
        return render_plan(preflight(self.root, brand_dir, niche))

    async def run(
        self,
        brand: str,
        niche: str,
        evidence: dict | None = None,
        progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> RunStatus:
        status = self.get_status(brand)
        evidence = evidence or {}
        brand_dir = initialize_brand(self.root, brand)
        try:
            status.current_stage = "preflight"
            checks = preflight(self.root, brand_dir, niche)
            status.completed.append("preflight")
            if progress:
                await progress("Stage 0/10: preflight complete")
            await self._stage(status, "research", self._research, evidence, progress)
            await self._stage(status, "pattern_mining", self._noop, evidence, progress)
            await self._stage(status, "concept_portfolio", self._concepts, evidence, progress)
            await self._stage(status, "psych_review", self._psych_review, evidence, progress)
            for stage in ("production", "judge_and_qa", "copy", "launch_plan"):
                await self._stage(status, stage, self._noop, evidence, progress)
            status.current_stage = "complete"
            return status
        except Exception as exc:
            status.error = str(exc)
            status.current_stage = "failed"
            raise

    async def readout(self, brand: str, evidence: dict) -> RunStatus:
        status = self.get_status(brand)
        status.current_stage = "readout"
        status.completed.append("readout")
        return status

    async def _stage(
        self,
        status: RunStatus,
        name: str,
        handler: Callable,
        evidence: dict,
        progress: Callable[[str], Awaitable[None]] | None,
    ) -> None:
        status.current_stage = name
        await handler(evidence)
        status.completed.append(name)
        if progress:
            await progress(f"Stage {len(status.completed) - 1}/10: {name} complete")

    async def _research(self, evidence: dict) -> None:
        seat = CreativeStrategist(client=self.client, model=self.model)
        await asyncio.to_thread(seat.mining_pass, evidence)

    async def _concepts(self, evidence: dict) -> None:
        seat = CreativeDirectorA(client=self.client, model=self.model)
        await asyncio.to_thread(seat.concept_portfolio, evidence)

    async def _psych_review(self, evidence: dict) -> None:
        assert_isolated_evidence(evidence)
        seat = EcommercePsychologist(client=self.client, model=self.model)
        await asyncio.to_thread(seat.psych_review, evidence)

    async def _noop(self, evidence: dict) -> None:
        await asyncio.sleep(0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", required=True)
    parser.add_argument("--niche", default="general")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    pipeline = Pipeline(Path.cwd())
    if args.dry_run:
        print(pipeline.preflight_plan(args.brand, args.niche))
    else:
        asyncio.run(pipeline.run(args.brand, args.niche))


if __name__ == "__main__":
    main()