"""The ten-stage creative pipeline (Doc 00 §3): preflight → … → launch plan, plus readout.

Stages 0-8 run from /run; Stage 9 (readout) is a separate trigger once spend exists. Runs
are resumable: batch state lives in brands/<brand>/05_creatives/B<NN>/batch.json, so a run
that stopped for missing human input (AwaitingInput) or a blocking gate (GateBlocked)
continues where it left off.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Awaitable, Callable

from agents.seats.analyst import Analyst

from . import gates
from .brand_state import (Batch, RESULTS_COLUMNS, append_learnings, append_results,
                          append_winning_variables, initialize_brand, load_profile,
                          open_or_new_batch, batch_ids, read)
from .economics import derived_targets_text
from .errors import AlreadyRunning, AwaitingInput, GateBlocked, StageError
from .imagegen import ImageSource, ManualImageSource
from .parsing import col, extract_json, parse_tables
from .stages import Ctx, Stages

STAGES = [
    "preflight", "research", "pattern_mining", "concept_portfolio", "psych_review",
    "production", "judge_and_qa", "copy", "launch_plan", "readout",
]
LABELS = {
    "preflight": "Preflight", "research": "Research", "pattern_mining": "Pattern mining",
    "concept_portfolio": "Concept portfolio", "psych_review": "Psych review",
    "production": "Production", "judge_and_qa": "Judge + QA", "copy": "Copy",
    "launch_plan": "Launch plan", "readout": "Readout",
}
Progress = Callable[[str], Awaitable[None]] | None


@dataclass
class RunStatus:
    brand: str
    batch: str | None = None
    current_stage: str = "idle"
    state: str = "idle"  # idle | running | complete | blocked | awaiting_input | failed
    completed: list[str] = field(default_factory=list)
    message: str = ""


class Pipeline(Stages):
    def __init__(self, root: Path, *, model: str = "claude-sonnet-4-6", client=None,
                 image_source: ImageSource | None = None, max_parallel: int = 3):
        self.root = Path(root)
        self.model = model
        self.client = client
        self.image_source = image_source or ManualImageSource()
        self.statuses: dict[str, RunStatus] = {}
        self._running: set[str] = set()
        self.max_parallel = max_parallel

    # ---------------------------------------------------------------- status
    def get_status(self, brand: str) -> RunStatus:
        if brand not in self.statuses:
            f = self.root / "brands" / brand / ".run-status.json"
            self.statuses[brand] = RunStatus(**json.loads(f.read_text())) if f.exists() else RunStatus(brand)
        return self.statuses[brand]

    def _save_status(self, status: RunStatus) -> None:
        d = self.root / "brands" / status.brand
        if d.exists():
            (d / ".run-status.json").write_text(json.dumps(asdict(status), indent=2))

    def is_running(self, brand: str) -> bool:
        return brand in self._running

    # -------------------------------------------------------------- Stage 0
    def preflight_plan(self, brand: str) -> str:
        brand_dir = initialize_brand(self.root, brand)
        profile = load_profile(brand_dir)
        items = gates.preflight(self.root, brand_dir, profile["niche"])
        return gates.render_plan(items, brand_dir, profile["niche"])

    # ------------------------------------------------------------- Stages 1-8
    async def run(self, brand: str, progress: Progress = None) -> RunStatus:
        if brand in self._running:
            raise AlreadyRunning(f"{brand} already has a run in progress")
        self._running.add(brand)
        status = self.get_status(brand)
        status.state, status.message, status.current_stage = "running", "", "preflight"
        batch: Batch | None = None

        async def say(msg: str) -> None:
            if progress:
                await progress(msg)

        try:
            brand_dir = initialize_brand(self.root, brand)
            profile = load_profile(brand_dir)
            batch = open_or_new_batch(brand_dir)
            status.batch, status.completed = batch.id, list(batch.completed)
            batch.status = "in_progress"
            items = gates.preflight(self.root, brand_dir, profile["niche"])
            await say("Stage 0/10: " + gates.render_plan(items, brand_dir, profile["niche"]))
            stop = gates.blocking(items)
            if stop:
                raise GateBlocked(f"{stop.name}: {stop.reason}")
            ctx = Ctx(self.root, brand, brand_dir, profile, batch, {i.name: i for i in items} | {
                "research": next(i for i in items if i.name == "research")})
            handlers = {
                "research": self.stage_research, "pattern_mining": self.stage_patterns,
                "concept_portfolio": self.stage_concepts, "psych_review": self.stage_psych,
                "production": self.stage_production, "judge_and_qa": self.stage_judge,
                "copy": self.stage_copy, "launch_plan": self.stage_launch,
            }
            for idx, name in enumerate(STAGES[1:9], start=1):
                if name in batch.completed:
                    continue
                status.current_stage = name
                self._save_status(status)
                msg = await handlers[name](ctx)
                batch.completed.append(name)
                status.completed = list(batch.completed)
                batch.save()
                await say(f"Stage {idx}/10: {LABELS[name]} — {msg}")
            status.state, status.current_stage = "complete", "complete"
            status.message = f"{batch.id} staged. Launch plan: 06_briefs-out/launch-plan-{batch.id}.md"
            batch.save()
            await say(status.message + " (proposal only — execute it manually, then /launched)")
        except GateBlocked as exc:
            status.state, status.message = "blocked", f"BLOCKED: {exc}"
            self._park(batch, "blocked")
            self._dump_last_output(brand)
            await say(status.message)
        except AwaitingInput as exc:
            status.state, status.message = "awaiting_input", f"NEEDS INPUT: {exc}"
            self._park(batch, "awaiting_input")
            await say(status.message)
        except Exception as exc:
            status.state, status.message = "failed", f"FAILED at {status.current_stage}: {exc}"
            self._park(batch, "blocked")
            self._dump_last_output(brand)
            await say(status.message)
            raise
        finally:
            self._save_status(status)
            self._running.discard(brand)
        return status

    def _dump_last_output(self, brand: str) -> None:
        """Keep the raw seat output of a failed/blocked run so a mismatch is diagnosed, not guessed at."""
        last = getattr(self, "last_output", None)
        if last:
            (self.root / "brands" / brand / "last-failed-seat-output.md").write_text(last)

    @staticmethod
    def _park(batch: Batch | None, state: str) -> None:
        if batch:
            batch.status = state
            batch.save()

    # -------------------------------------------------------------- Stage 9
    async def readout(self, brand: str, progress: Progress = None) -> RunStatus:
        """Separate trigger. The orchestrator never calls the Analyst without the spend-floor check."""
        if brand in self._running:
            raise AlreadyRunning(f"{brand} already has a run in progress")
        self._running.add(brand)
        status = self.get_status(brand)
        status.state, status.current_stage, status.message = "running", "readout", ""
        try:
            msg = await self._readout(brand)
            status.state, status.message = "complete", f"Stage 9/10: Readout — {msg}"
        except GateBlocked as exc:
            status.state, status.message = "blocked", f"BLOCKED: {exc}"
        except AwaitingInput as exc:
            status.state, status.message = "awaiting_input", f"NEEDS INPUT: {exc}"
        except Exception as exc:
            status.state, status.message = "failed", f"FAILED at readout: {exc}"
            raise
        finally:
            self._save_status(status)
            self._running.discard(brand)
            if progress:
                await progress(status.message)
        return status

    async def _readout(self, brand: str) -> str:
        brand_dir = initialize_brand(self.root, brand)
        profile = load_profile(brand_dir)
        exports = brand_dir / "07_results" / "exports"
        names = {"ads_3d": "ads-3d.csv", "ads_7d": "ads-7d.csv", "ads_lifetime": "ads-lifetime.csv",
                 "country_breakdown": "country.csv"}
        data = {k: read(exports / f) for k, f in names.items()}
        absent = [names[k] for k, v in data.items() if not v]
        if absent:
            raise AwaitingInput(f"export the ad-level and country data into {exports}: {', '.join(absent)}")
        ok, why = gates.spend_floor_gate(list(csv.DictReader(io.StringIO(data["ads_lifetime"]))),
                                         profile.get("target_cpa"))
        if not ok:
            raise GateBlocked(why)
        econ = derived_targets_text(profile.get("economics"), profile.get("target_cpa"))
        ledger = read(self.root / "shared" / "creative-ledger.md")
        res = await self.call(self.seat(Analyst).readout, {
            "brand": brand, "week_of": date.today().isoformat(), **data,
            "economics": econ + "\n\n" + json.dumps(profile.get("economics") or "unknown"),
            "creative_ledger": ledger if "## " in ledger else "nothing shipped yet",
            "results_log": read(brand_dir / "07_results" / "results-log.md")})
        result, prose = extract_json(res.output_text)
        ads, notes = gates.enforce_spend_floor(result.get("ads", []), profile.get("target_cpa"))
        launched = [i for i in batch_ids(brand_dir) if Batch.load(brand_dir, i).status == "launched"]
        covered = {str(a.get("batch")) for a in ads}
        unresolved = [b for b in launched if b not in covered]
        if unresolved:
            (brand_dir / "07_results" / f"readout-{date.today()}-REJECTED.md").write_text(prose)
            raise GateBlocked(f"readout does not reconcile: {unresolved} have no verdict, below-floor "
                              "or NOT LAUNCHED rows")
        rows = [[a.get("date") or date.today().isoformat(), f"{a.get('ad_name', '')} / {a.get('ad_id', '')}",
                 a.get("batch", "UNMAPPED"), a.get("concept", ""), a.get("campaign_type", ""),
                 a.get("spend", ""), _dash(a.get("purchases")), _dash(a.get("cpa")), _dash(a.get("roas")),
                 _dash(a.get("ctr")), _dash(a.get("freq")), a.get("verdict", ""), a.get("action_taken", "")]
                for a in ads]
        append_results(brand_dir, rows)
        kept = append_winning_variables(self.root, brand, result.get("winning_variables", []))
        append_learnings(self.root, brand, result.get("learnings", []))
        flag = brand_dir / "07_results" / "invalidate-research.flag"
        if result.get("invalidate_research"):
            flag.write_text(f"invalidated by readout {date.today()}\n")
        report = brand_dir / "07_results" / f"readout-{date.today()}.md"
        report.write_text(prose + ("\n\n## Orchestrator notes\n" + "\n".join(f"- {n}" for n in notes) if notes else "") + "\n")
        self._update_angle_performance(brand_dir)
        return f"{len(rows)} rows logged, {kept} winning variables promoted" + (
            f", {len(notes)} spend-floor corrections" if notes else "")

    @staticmethod
    def _update_angle_performance(brand_dir: Path) -> None:
        """Aggregate the latest row per ad by angle family (mapped through each batch's concept table)."""
        log = read(brand_dir / "07_results" / "results-log.md")
        rows = next(iter(parse_tables(log)), [])
        family: dict[str, str] = {}
        for bid in batch_ids(brand_dir):
            for c in Batch.load(brand_dir, bid).concepts.values():
                family[f"{bid}|{re.sub(r'[^a-z0-9]', '', col(c, 'concept name').lower())}"] = col(c, "angle")
        latest = {r.get("ad name / id"): r for r in rows}
        agg: dict[str, dict] = {}
        for r in latest.values():
            key = f"{r.get('batch')}|{re.sub(r'[^a-z0-9]', '', r.get('concept', '').lower())}"
            a = agg.setdefault(family.get(key, "UNMAPPED"), {"ads": 0, "spend": 0.0, "purch": 0.0, "rs": 0.0, "v": {}})
            spend = gates._num(r.get("spend")) or 0.0
            a["ads"] += 1; a["spend"] += spend; a["purch"] += gates._num(r.get("purch")) or 0.0
            a["rs"] += spend * (gates._num(r.get("ROAS")) or 0.0)
            a["v"][r.get("verdict", "")] = a["v"].get(r.get("verdict", ""), 0) + 1
        from .brand_state import ANGLE_COLUMNS, _table_header
        lines = ["# Angle performance\n", _table_header(ANGLE_COLUMNS).rstrip("\n")]
        for fam, a in sorted(agg.items()):
            cpa = f"{a['spend'] / a['purch']:.2f}" if a["purch"] else "-"
            roas = f"{a['rs'] / a['spend']:.2f}" if a["spend"] else "-"
            lines.append(f"| {fam} | {a['ads']} | {a['spend']:.2f} | {a['purch']:.0f} | {cpa} | {roas} | "
                         + ", ".join(f"{k}×{n}" for k, n in a["v"].items()) + " |")
        (brand_dir / "07_results" / "angle-performance.md").write_text("\n".join(lines) + "\n")


def _dash(v) -> str:
    return "-" if v is None else str(v)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the creative pipeline for a brand")
    parser.add_argument("--brand", required=True)
    parser.add_argument("--dry-run", action="store_true", help="print the Stage 0 plan and stop")
    parser.add_argument("--init", action="store_true", help="create the brand tree and brand.json stub")
    parser.add_argument("--readout", action="store_true", help="run Stage 9 only")
    args = parser.parse_args()
    from config.settings import load_settings
    settings = load_settings()
    pipeline = Pipeline(Path.cwd(), model=settings.model)

    async def say(msg: str) -> None:
        print(msg)

    try:
        if args.init:
            print(f"initialized {initialize_brand(Path.cwd(), args.brand)}")
        elif args.dry_run:
            print(pipeline.preflight_plan(args.brand))
        elif args.readout:
            asyncio.run(pipeline.readout(args.brand, say))
        else:
            asyncio.run(pipeline.run(args.brand, say))
    except (AwaitingInput, GateBlocked) as exc:
        raise SystemExit(f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
