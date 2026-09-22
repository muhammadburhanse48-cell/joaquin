"""Stage implementations for the ten-stage loop (Doc 00 §3).

Each stage reads its evidence from files, calls its seat(s) with an explicit evidence dict,
writes the seat's output to the brand/shared files, and enforces its gates in code. Stages
never hand one seat another seat's reasoning: critics receive images and files only.
"""

from __future__ import annotations

import asyncio
import contextvars
import csv
import io
import json
import re
import shutil
import threading
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from agents.seats.copy_editor import CopyEditor
from agents.seats.copywriter import Copywriter
from agents.seats.creative_director_a import CreativeDirectorA
from agents.seats.creative_director_b import CreativeDirectorB
from agents.seats.creative_strategist import CreativeStrategist
from agents.seats.ecommerce_psychologist import EcommercePsychologist
from agents.seats.graphic_designer import GraphicDesigner
from agents.seats.media_buyer import MediaBuyer
from agents.seats.opportunity_scout import OpportunityScout

from . import gates
from .brand_state import (Batch, append_ledger, atomic_write, has_content,
                          latest_account_report, read, slug)
from .economics import derived_targets_text
from .errors import AwaitingInput, GateBlocked, StageError
from .imagegen import IMAGE_SUFFIXES, candidates
from .parsing import (col, extract_json, json_objects, parse_tables, render_table, rows_to_csv,
                      split_named_files, unverified_quotes)

COPY_COLUMNS = ["#", "concept", "angle", "persona", "file_1x1", "on_image", "primary_text",
                "headline", "cta", "link"]
SOURCE_FILES = {
    "own_reviews": "own-reviews.md",
    "competitor_reviews": "competitor-reviews.md",
    "ad_comments": "ad-comments.md",
    "forum_threads": "forum-threads.md",
    "competitor_ad_copy": "competitor-ad-copy.md",
    "own_ads": "own-ads.md",
}
NONE_ON_FILE = "none on file"
# Models write "## Persona: Name", "## Persona 1: Name", "### Persona 2 — Name": accept all.
PERSONA_HEADING = r"#{2,3}\s+Persona\b(?!s)[^\n]*"
QUOTE_AUDIT_MAX_BAD = 0.25

# (brand, stage) of the coroutine currently making seat calls — set by Pipeline.run's run_one
# wrapper so a failed call's output and usage are attributed to the stage that actually failed,
# never a stage or brand running concurrently in the same process (the bot shares one Pipeline).
CURRENT_STAGE: contextvars.ContextVar[tuple[str, str]] = contextvars.ContextVar(
    "CURRENT_STAGE", default=("?", "?"))


def _rate_limit_retry_after(exc: BaseException, default: float = 5.0) -> float | None:
    """None if `exc` isn't a rate-limit/overload error; otherwise how long to pause every
    other concurrent seat call before letting new ones start (the server's Retry-After header
    if it gave one, else a fixed backoff). Duck-typed, not an `isinstance(exc, anthropic...)`
    check, so this has no hard import-time dependency on the anthropic package."""
    status = getattr(exc, "status_code", None)
    if status not in (429, 529) and type(exc).__name__ not in ("RateLimitError", "InternalServerError"):
        return None
    header = getattr(getattr(exc, "response", None), "headers", {}) or {}
    try:
        return float(header.get("retry-after", default))
    except (TypeError, ValueError):
        return default


@dataclass
class Ctx:
    root: Path
    brand: str
    brand_dir: Path
    profile: dict
    batch: Batch
    plan: dict  # PlanItem by name

    @property
    def niche(self) -> str:
        return self.profile["niche"]

    @property
    def offer_text(self) -> str:
        p = self.profile
        return (f"Brand: {self.brand}\nProduct: {p['product']}\nOffer: {p['offer']}\n"
                f"Required qualifier on any 'free' / '$0': {p['offer_qualifier']}\nMarket: {p['market']}")

    @property
    def brand_rules(self) -> str:
        p = self.profile
        pal = p["palette"]
        banned = ", ".join(p.get("banned_words") or []) or "none listed"
        return (f"Palette: ground {pal['ground']} / accent {pal['accent']} / contrast {pal['contrast']}\n"
                f"Banned words: {banned}\nOffer qualifier: {p['offer_qualifier']}")


def _or_none(text: str, label: str = NONE_ON_FILE) -> str:
    return text.strip() if text and text.strip() else label


def persona_card_for(cards: str, persona: str) -> str:
    """The card whose heading best matches the concept's persona; all cards if none matches."""
    parts = [p for p in re.split(rf"(?m)^(?={PERSONA_HEADING})", cards) if re.match(PERSONA_HEADING, p.lstrip())]
    tokens = {t for t in re.findall(r"[a-z0-9]{3,}", persona.lower())}
    best, score = None, 0
    for p in parts:
        overlap = len(tokens & set(re.findall(r"[a-z0-9]{3,}", p.splitlines()[0].lower())))
        if overlap > score:
            best, score = p, overlap
    return (best or cards).strip()


def visual_world(card: str) -> str:
    """The card's 'Visual world' text, whether the model wrote a bullet or a heading."""
    m = re.search(r"(?im)^[#>\-* ]*\**visual world\**[^\n]*?(?::\**\s*(.*))?$", card)
    if not m:
        return re.sub(r"\s+", " ", card)[:400]
    rest = card[m.end():]
    stop = re.search(r"(?m)^(#{1,4} |[-*] \**[A-Z][^:\n]{0,40}:)", rest)
    text = ((m.group(1) or "") + " " + rest[: stop.start() if stop else len(rest)]).strip()
    return re.sub(r"\s+", " ", text)[:700] or re.sub(r"\s+", " ", card)[:400]


class Stages:
    """Mixin for Pipeline. Expects: root, model, client, image_source, max_parallel."""

    # ---------------------------------------------------------------- plumbing
    def seat(self, cls, **kw):
        return cls(client=self.client, model=self.model, **kw)

    async def call(self, fn: Callable, *a, **kw):
        loop = asyncio.get_running_loop()
        if getattr(self, "_sem_loop", None) is not loop:  # this state belongs to one event loop
            self._sem_loop = loop
            self._sem = asyncio.Semaphore(self.max_parallel)
            self._cooldown = asyncio.Event()
            self._cooldown.set()
        # A sibling's 429 pauses everyone briefly before they queue on the semaphore — the SDK's
        # own max_retries backs off per-request, but under fan-out every worker hits the limit
        # independently and would otherwise all retry in lockstep. This never blocks the request
        # that is already in flight, only new ones about to start.
        await self._cooldown.wait()
        async with self._sem:
            try:
                res = await asyncio.to_thread(fn, *a, **kw)
            except Exception as exc:
                retry_after = _rate_limit_retry_after(exc)
                if retry_after is not None and self._cooldown.is_set():
                    self._cooldown.clear()
                    try:
                        await asyncio.sleep(retry_after)
                    finally:
                        self._cooldown.set()
                raise
        self._record_output(res)
        return res

    def _record_output(self, res: Any) -> None:
        stage_key = CURRENT_STAGE.get()
        text = getattr(res, "output_text", None)
        if text is not None:
            lock = self.__dict__.setdefault("_last_output_lock", threading.Lock())
            with lock:
                self.__dict__.setdefault("_last_output", {})[stage_key] = text
        usage = getattr(getattr(res, "raw_response", None), "usage", None)
        if usage is not None:
            lock = self.__dict__.setdefault("_usage_lock", threading.Lock())
            with lock:
                store = self.__dict__.setdefault("_usage", {})
                cur = store.setdefault(stage_key, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
                cur["calls"] += 1
                cur["input_tokens"] += getattr(usage, "input_tokens", 0) or 0
                cur["output_tokens"] += getattr(usage, "output_tokens", 0) or 0

    def last_output_for(self, brand: str, stage: str) -> str | None:
        """The most recent seat output for this (brand, stage), or None. Keyed, not a single
        shared attribute, because the bot runs one Pipeline for every brand and a stage can
        run beside another (Phase 1 waves) — a plain `self.last_output` would race."""
        return self.__dict__.get("_last_output", {}).get((brand, stage))

    def usage_for(self, brand: str, stage: str) -> dict:
        return self.__dict__.get("_usage", {}).get(
            (brand, stage), {"calls": 0, "input_tokens": 0, "output_tokens": 0})

    def usage_summary(self, brand: str) -> dict:
        """Total calls/tokens across every stage this Pipeline has recorded for `brand`."""
        total = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        for (b, _stage), u in self.__dict__.get("_usage", {}).items():
            if b == brand:
                for k in total:
                    total[k] += u[k]
        return total

    def _research_ev(self, ctx: Ctx) -> dict:
        r = ctx.brand_dir / "03_research"
        files = {"persona_cards": r / "persona-cards.md", "customer_language": r / "customer-language.md",
                 "market_diagnosis": r / "market-diagnosis.md",
                 "angle_bank": ctx.brand_dir / "04_angles-scripts" / "angle-bank.md"}
        missing = [p.name for p in files.values() if not has_content(p)]
        if missing:
            raise GateBlocked(f"research files missing or empty: {', '.join(missing)} "
                              "(no persona cards, no concepts)")
        return {k: read(p) for k, p in files.items()}

    def _results_log(self, ctx: Ctx) -> str:
        text = read(ctx.brand_dir / "07_results" / "results-log.md")
        tables = parse_tables(text)
        return text if tables and tables[0] else "none — no batch has been read out yet"

    def _ledger(self, ctx: Ctx) -> str:
        text = read(ctx.root / "shared" / "creative-ledger.md")
        return text if "## " in text else "nothing shipped yet"

    def _shipped_copy(self, ctx: Ctx) -> str:
        chunks = []
        for f in sorted((ctx.brand_dir / "05_creatives").glob("B*/B*_COPY-SHEET.csv")):
            if f.parent.name != ctx.batch.id:
                chunks.append(f"{f.name}\n{f.read_text()}")
        return "\n".join(chunks) or "none — first batch"

    def _manifest(self, ctx: Ctx) -> list[dict]:
        f = ctx.root / "shared" / "swipe-vault" / ctx.niche / "manifest.json"
        return json.loads(f.read_text()) if f.exists() else []

    # ------------------------------------------------------------- Stage 1: research
    def _sources(self, ctx: Ctx) -> dict:
        d = ctx.brand_dir / "03_research" / "source"
        got = {k: read(d / f) for k, f in SOURCE_FILES.items()}
        if sum(1 for v in got.values() if v) < 2:
            raise AwaitingInput(
                f"put raw source material in {d} — at least two non-empty of: "
                f"{', '.join(SOURCE_FILES.values())} (own store reviews first; include the 1-3 star ones)")
        return {k: v or "none provided" for k, v in got.items()}

    async def stage_research(self, ctx: Ctx) -> str:
        if ctx.plan["research"].action == "REUSE":
            return "reused — research files are fresh"
        src, p = self._sources(ctx), ctx.profile
        raw = "\n".join(f"--- {k.upper()} ---\n{v}" for k, v in src.items() if v != "none provided")
        seat = self.seat(CreativeStrategist)
        mining = (await self.call(seat.mining_pass, {
            "brand": ctx.brand, "product": p["product"], "market": p["market"],
            "buyer_guess": p["buyer_guess"], **src})).output_text
        files = split_named_files(mining, ["customer-language.md", "market-diagnosis.md"])
        bad, total = unverified_quotes(files["customer-language.md"], raw)
        r = ctx.brand_dir / "03_research"
        (r / "quote-audit.md").write_text(
            f"# Quote audit (Law 1)\n\n{total - len(bad)}/{total} quoted strings found verbatim in the "
            f"source material.\n\nNot found:\n" + "".join(f"- {q}\n" for q in bad))
        if total and len(bad) / total > QUOTE_AUDIT_MAX_BAD:
            (r / "mining-pass-rejected.md").write_text(mining)
            raise GateBlocked(f"{len(bad)}/{total} quotes in customer-language.md are not in the source "
                              "material — invented quotes are a defect; see 03_research/quote-audit.md")
        (r / "customer-language.md").write_text(files["customer-language.md"] + "\n")
        (r / "market-diagnosis.md").write_text(files["market-diagnosis.md"] + "\n")
        base = {"customer_language": files["customer-language.md"],
                "market_diagnosis": files["market-diagnosis.md"], "source_material": raw}
        cards = (await self.call(seat.persona_cards, base)).output_text
        n_personas = len(re.findall(rf"(?m)^{PERSONA_HEADING}", cards))
        if not n_personas:
            raise StageError("persona-cards output has no '## Persona …' cards")
        (r / "persona-cards.md").write_text(cards.strip() + "\n")
        angles = (await self.call(seat.angle_bank, {
            **base, "persona_cards": cards, "creative_ledger": self._ledger(ctx)})).output_text
        (ctx.brand_dir / "04_angles-scripts" / "angle-bank.md").write_text(angles.strip() + "\n")
        (ctx.brand_dir / "07_results" / "invalidate-research.flag").unlink(missing_ok=True)
        ok, why = gates.research_freshness_gate(ctx.brand_dir)
        if not ok:
            raise GateBlocked(f"research gate still failing after refresh: {why}")
        return f"customer language, market diagnosis, {n_personas} persona cards, " \
               f"{len(re.findall(r'(?m)^### A', angles))} angles"

    # ------------------------------------------------------ Stage 2: pattern mining
    async def stage_patterns(self, ctx: Ctx) -> str:
        name = "pattern library + swipe vault"
        if ctx.plan[name].action == "REUSE":
            return "reused — library and swipe vault are fresh"
        niche = ctx.niche
        vault = ctx.root / "shared" / "swipe-vault" / niche
        inc = vault / "incoming"
        images = sorted(p for p in inc.glob("*") if p.suffix.lower() in IMAGE_SUFFIXES) if inc.exists() else []
        ev_file = inc / "evidence.md"
        if len(images) < 15 or not ev_file.exists():
            raise AwaitingInput(
                f"pattern mining reads images (hard gate: at least 15, ideally 25-40 winners from 8+ "
                f"advertisers). Put them in {inc} and write {ev_file.name} with one line per image: "
                "'image 01 — advertiser: <domain> · <US: 94 days running, 6 variants> or <EU: €7,645>'. "
                f"Found {len(images)} images.")
        lines = {m.group(1): m.group(0) for m in
                 re.finditer(r"(?m)^image (\d{2})\s*—.*$", ev_file.read_text())}
        absent = [f"{i:02d}" for i in range(1, len(images) + 1) if f"{i:02d}" not in lines]
        if absent:
            raise AwaitingInput(f"{ev_file.name} has no evidence line for image(s) {', '.join(absent)}")
        scout = self.seat(OpportunityScout)
        batches = [[f"{i:02d}" for i in range(start + 1, min(start + 8, len(images)) + 1)]
                  for start in range(0, len(images), 8)]
        # Each 8-image batch is an independent scout.visual_teardown call — run them concurrently.
        # asyncio.gather returns results in ARGUMENT order (not completion order), so flattening
        # keeps the rows in image order regardless of which batch's call returns first; row order
        # is load-bearing downstream (pattern_mining's table, and the manifest maps entries back
        # to images[n-1]).
        outs = await asyncio.gather(*(self._teardown_batch(scout, niche, lines, images, nums)
                                      for nums in batches))
        rows: list[dict] = [r for out in outs for r in out]
        table = render_table(rows, list(rows[0]))
        advertisers = {m.group(1) for m in re.finditer(r"advertiser:\s*(\S+)", "\n".join(lines.values()))}
        lib = (await self.call(scout.pattern_mining, {
            "niche": niche, "n_rows": len(rows), "n_advertisers": len(advertisers) or 1,
            "teardown_rows": table})).output_text
        today = date.today()
        header = (f"# Visual Pattern Library — {niche}\nRun date: {today} · Ads analysed: {len(rows)} · "
                  f"Advertisers: {len(advertisers)} · STALE AFTER: {today + timedelta(days=30)}\n\n")
        lib_path = gates.pattern_library_path(ctx.root, niche)
        atomic_write(lib_path, header + lib.strip() + "\n")
        sel = (await self.call(scout.swipe_vault, {
            "n_images": len(rows), "teardown_rows": table, "pattern_library": lib,
            "evidence_per_image": "\n".join(lines.values())})).output_text
        entries = [o for o in json_objects(sel) if "file" in o and "source_ad_id" in o]
        if not 8 <= len(entries) <= 15:
            (vault / "selection-rejected.md").write_text(sel)
            raise StageError(f"swipe vault selection has {len(entries)} manifest entries (need 8-15)")
        for e in entries:
            n = re.match(r"(\d+)", e["file"])
            if not n or not 1 <= int(n.group(1)) <= len(images):
                raise StageError(f"manifest file {e['file']!r} does not map to an analysed image")
            src = images[int(n.group(1)) - 1]
            e["file"] = Path(e["file"]).with_suffix(src.suffix.lower()).name
            shutil.copy2(src, vault / e["file"])
        atomic_write(vault / "manifest.json", json.dumps(entries, indent=2, ensure_ascii=False))
        (vault / "selection-notes.md").write_text(sel)
        ok, why = gates.pattern_gate(ctx.root, niche)
        if not ok:
            raise GateBlocked(f"pattern gate still failing after mining: {why}")
        return f"{len(rows)} ads analysed, {len(entries)} swipe-vault images"

    async def _teardown_batch(self, scout: OpportunityScout, niche: str, lines: dict[str, str],
                              images: list[Path], nums: list[str]) -> list[dict]:
        """One independent visual_teardown call over up to 8 images. Caller gathers these
        concurrently and relies on asyncio.gather's argument-order guarantee to keep rows
        in image order — do not reorder or complete-order-sort the results here."""
        out = (await self.call(
            scout.visual_teardown,
            {"niche": niche, "evidence_per_image": "\n".join(lines[n] for n in nums)},
            [(f"image {n}", images[int(n) - 1].read_bytes()) for n in nums])).output_text
        got = next(iter(parse_tables(out)), [])
        if len(got) != len(nums):
            raise StageError(f"teardown returned {len(got)} rows for images {nums[0]}-{nums[-1]}")
        return got

    # ------------------------------------------------ Stage 3: concept portfolio
    async def stage_concepts(self, ctx: Ctx) -> str:
        ev = self._research_ev(ctx)
        lib = read(gates.pattern_library_path(ctx.root, ctx.niche))
        if ctx.batch.concepts:  # resuming after a block: the portfolio was already paid for and passed
            results = await asyncio.gather(*(self._briefs_for(ctx, c, ev, lib) for c in ctx.batch.concepts))
            return f"{len(ctx.batch.concepts)} concepts (resumed), {sum(results)} briefs"
        report = latest_account_report(ctx.brand_dir)
        radar = [r for t in parse_tables(read(ctx.root / "shared" / "format-radar.md")) for r in t
                 if col(r, "NICHE").lower() == ctx.niche.lower()]
        seat = self.seat(CreativeDirectorA)
        res = await self.call(seat.concept_portfolio, {
            "account_report": _or_none(read(report) if report else "", "none on file (no live ads yet)"),
            "results_log": self._results_log(ctx), "persona_cards": ev["persona_cards"],
            "customer_language": ev["customer_language"], "market_diagnosis": ev["market_diagnosis"],
            "angle_bank": ev["angle_bank"], "pattern_library": lib,
            "format_radar": render_table(radar, list(radar[0])) if radar else "none on file",
            "creative_ledger": self._ledger(ctx), "batch": ctx.batch.id[1:]})
        (ctx.batch.dir / "concepts.md").write_text(res.output_text)
        tables = parse_tables(res.output_text)
        rows = max(tables, key=len) if tables else []
        ok, why = gates.portfolio_gate(rows, gates.CONCEPTS_PER_BATCH)
        if not ok:
            raise GateBlocked(f"concept portfolio rejected: {why} (see concepts.md)")
        for i, row in enumerate(rows, 1):
            row["#"] = f"{i:02d}"
            ctx.batch.concepts[f"{i:02d}"] = row
        (ctx.batch.dir / "concept-table.md").write_text(render_table(rows, list(rows[0])) + "\n")
        ctx.batch.save()
        results = await asyncio.gather(*(self._briefs_for(ctx, c, ev, lib) for c in ctx.batch.concepts))
        return f"{len(rows)} concepts, {sum(results)} briefs ({why.split(', ', 1)[1]})"

    async def _briefs_for(self, ctx: Ctx, cnum: str, ev: dict, lib: str, fix: str | None = None) -> int:
        """Write (or, with `fix`, revise) the briefs for one concept: one per variant."""
        row, V = ctx.batch.concepts[cnum], int(ctx.profile["variants_per_concept"])
        existing = {nn: s for nn, s in ctx.batch.slots.items() if s["concept"] == cnum}
        if not fix and len(existing) == V and all(
                (ctx.batch.dir / "briefs" / s["brief"]).exists() for s in existing.values() if s.get("brief")):
            return len(existing)  # briefs already written and gated on an earlier run
        base = {"concept_number": cnum, "batch": ctx.batch.id[1:], "variants": V,
                "concept_row": render_table([row], list(row)), "offer": ctx.offer_text,
                "persona_cards": ev["persona_cards"], "customer_language": ev["customer_language"],
                "angle_bank": ev["angle_bank"], "pattern_library": lib,
                "swipe_manifest": json.dumps(self._manifest(ctx)) or NONE_ON_FILE,
                "creative_ledger": self._ledger(ctx)}
        seat = self.seat(CreativeDirectorA)
        chunks: list[str] = []
        for attempt in range(2):
            if fix:
                current = "\n\n".join((ctx.batch.dir / "briefs" / s["brief"]).read_text()
                                      for s in existing.values())
                res = await self.call(seat.revise_briefs, {**base, "psych_fix": fix, "current_briefs": current})
            else:
                res = await self.call(seat.write_briefs, base)
            chunks = [c for c in re.split(r"(?m)^(?=# Creative Brief)", res.output_text)
                      if c.lstrip().startswith("# Creative Brief")]
            problems = [gates.brief_gate(c)[1] for c in chunks if not gates.brief_gate(c)[0]]
            if len(chunks) == V and not problems:
                break
        else:
            raise GateBlocked(f"no brief, no production — concept {cnum}: expected {V} complete briefs, "
                              f"got {len(chunks)}; {'; '.join(problems) or 'wrong count'}")
        name = slug(col(row, "concept name"))
        for v, text in enumerate(chunks, 1):
            nn = f"{(int(cnum) - 1) * V + v:02d}"
            fname = f"{nn}_{slug(ctx.brand)}_{name}_v{v}.md"
            (ctx.batch.dir / "briefs" / fname).write_text(text.strip() + "\n")
            slot = ctx.batch.slots.get(nn) or {"concept": cnum, "variant": v, "round": 1,
                                               "judged_round": 0, "state": "open"}
            slot["brief"] = fname
            ctx.batch.slots[nn] = slot
        ctx.batch.save()
        return len(chunks)

    # ------------------------------------------------------ Stage 4: psych review
    async def stage_psych(self, ctx: Ctx) -> str:
        ev = self._research_ev(ctx)
        rows = list(ctx.batch.concepts.values())
        # The critic gets the concept TABLE only: never the director's reasoning or the briefs.
        evidence = {
            "concept_portfolio": render_table(rows, list(rows[0])),
            "persona_cards": ev["persona_cards"], "customer_language": ev["customer_language"],
            "market_diagnosis": ev["market_diagnosis"], "results_log": self._results_log(ctx),
            "landing_page": ctx.profile["landing_page_promise"]}
        seat = self.seat(EcommercePsychologist)
        res = await self.call(seat.psych_review, evidence)  # run() asserts isolation
        verdicts, prose = extract_json(res.output_text)
        (ctx.batch.dir / "psych-review.md").write_text(prose + "\n")
        by = {f"{int(v['concept']):02d}": v for v in verdicts if str(v.get("concept", "")).strip().isdigit()}
        absent = [c for c in ctx.batch.concepts if c not in by]
        if absent:
            raise StageError(f"psych review returned no verdict for concepts {absent}")
        lib = read(gates.pattern_library_path(ctx.root, ctx.niche))
        fixes = []
        for cnum, v in by.items():
            kind = str(v.get("verdict", "")).upper()
            if kind == "SWAP":
                ctx.batch.excluded[cnum] = v.get("fix") or "swap requested"
                for nn in [n for n, s in ctx.batch.slots.items() if s["concept"] == cnum]:
                    ctx.batch.slots[nn]["state"] = "excluded"
            elif kind == "FIX":
                fixes.append(self._briefs_for(ctx, cnum, ev, lib, fix=v.get("fix") or "apply the review's fix"))
        await asyncio.gather(*fixes)  # the author may see the critic's fix; one pass, no loop
        ctx.batch.save()
        if not any(s["state"] == "open" for s in ctx.batch.slots.values()):
            raise GateBlocked("psych review swapped out every concept; nothing left to produce")
        tally = {k: sum(1 for v in by.values() if str(v.get("verdict")).upper() == k)
                 for k in ("PASS", "FIX", "SWAP")}
        return f"{tally['PASS']} PASS / {tally['FIX']} FIX / {tally['SWAP']} SWAP" + (
            f" — SWAP concepts need replacements: {sorted(ctx.batch.excluded)}" if ctx.batch.excluded else "")

    # ------------------------------------------------------------ Stage 5: production
    def _product_photo(self, ctx: Ctx) -> Path:
        d = ctx.brand_dir / "_product-assets"
        photos = sorted(p for p in d.glob("*") if p.suffix.lower() in IMAGE_SUFFIXES)
        if not photos:
            raise AwaitingInput(f"put the REAL product photograph(s) in {d} — every generation and "
                                "every QA needs it as a reference")
        return photos[0]

    def _round_dir(self, ctx: Ctx, nn: str, rnd: int) -> Path:
        return ctx.batch.dir / "candidates" / nn / f"r{rnd}"

    def _brief(self, ctx: Ctx, nn: str) -> str:
        return (ctx.batch.dir / "briefs" / ctx.batch.slots[nn]["brief"]).read_text()

    def _image_semaphore(self) -> asyncio.Semaphore:
        """A semaphore separate from Stages._sem: image-generation APIs have their own, much
        lower rate limits than text, so they must not share the text semaphore's budget."""
        loop = asyncio.get_running_loop()
        if getattr(self, "_img_sem_loop", None) is not loop:
            self._img_sem_loop = loop
            self._img_sem = asyncio.Semaphore(self.max_parallel_images)
        return self._img_sem

    async def _ensure_candidates(self, ctx: Ctx) -> int:
        """2-3 candidates for every open slot's current round, or stop with AwaitingInput."""
        photo = self._product_photo(ctx)
        cards = self._research_ev(ctx)["persona_cards"]
        gd = self.seat(GraphicDesigner)
        cps = int(ctx.profile["candidates_per_slot"])
        # Pass A — sequential, no model/generator I/O: build every open slot's prompt and
        # spec.json in slot order. Keeps prompt-writing order deterministic and independent of
        # generation timing.
        jobs: list[tuple[str, Path, str]] = []
        for nn, s in sorted(ctx.batch.slots.items()):
            if s["state"] != "open":
                continue
            rdir = self._round_dir(ctx, nn, s["round"])
            if len(candidates(rdir)) >= 2:
                continue
            rdir.mkdir(parents=True, exist_ok=True)
            brief, row, p = self._brief(ctx, nn), ctx.batch.concepts[s["concept"]], ctx.profile
            copy = gates.copy_slots(brief)
            card = persona_card_for(cards, col(row, "persona"))
            spec = {"product_features": p["product_features"], "product_noun": p["product_noun"],
                    "background": p["background"], "niche_tone": p["niche_tone"],
                    "palette_ground": p["palette"]["ground"], "palette_accent": p["palette"]["accent"],
                    "palette_contrast": p["palette"]["contrast"], "persona_visual_world": visual_world(card),
                    "qualifier": p["offer_qualifier"], **{k: copy[k] for k in gates.COPY_SLOTS if k in copy}}
            req = gd.build_prompt(spec, photo.name)
            prompt = req.prompt
            if s.get("fix"):
                prompt += ("\n\n[REGENERATION FIX from the judge — apply exactly, change nothing else]\n"
                           f"{s['fix']}")
            (ctx.batch.dir / "prompts" / f"{nn}_r{s['round']}.md").write_text(
                f"Attach as reference: {photo}\n\n{prompt}\n")
            (rdir / "spec.json").write_text(json.dumps(req.sidecar, indent=2, ensure_ascii=False))
            jobs.append((nn, rdir, prompt))
        # Pass B — every slot's generation call is independent of every other slot's; run them
        # concurrently under a dedicated (lower) semaphore. return_exceptions so one slot's
        # AwaitingInput (or a real generator error) doesn't cancel the rest.
        async def _generate(nn: str, rdir: Path, prompt: str) -> None:
            async with self._image_semaphore():
                await asyncio.to_thread(self.image_source.generate, prompt, photo, cps, rdir)

        results = await asyncio.gather(*(_generate(nn, rdir, prompt) for nn, rdir, prompt in jobs),
                                       return_exceptions=True)
        # A real (non-AwaitingInput) generator error must not be swallowed as "needs images" —
        # surface the first one, in slot order.
        for (nn, rdir, _), r in zip(jobs, results):
            if isinstance(r, Exception) and not isinstance(r, AwaitingInput):
                raise r
        need = [f"{rdir.relative_to(ctx.brand_dir)} ({cps} images)"
               for (nn, rdir, _), r in zip(jobs, results) if isinstance(r, AwaitingInput)]
        made = sum(1 for r in results if not isinstance(r, BaseException))
        if need:
            raise AwaitingInput(
                f"{len(need)} slot(s) need candidate images. Generation prompts are in "
                f"{(ctx.batch.dir / 'prompts').relative_to(ctx.brand_dir)}/ (attach the product photo "
                "to every generation). Add 2-3 candidates to: " + "; ".join(need[:6])
                + (" …" if len(need) > 6 else "") + " — then run again.")
        return made

    async def stage_production(self, ctx: Ctx) -> str:
        await self._ensure_candidates(ctx)
        open_n = sum(1 for s in ctx.batch.slots.values() if s["state"] == "open")
        return f"candidates ready for {open_n} creative slots"

    # ----------------------------------------------------- Stage 6: judge and QA
    def _exemplar(self, ctx: Ctx, archetype: str) -> tuple[bytes | None, str]:
        manifest = self._manifest(ctx)
        if not manifest:
            return None, "no swipe-vault exemplar available"
        a = archetype.lower()
        pick = next((m for m in manifest if a and a in str(m.get("format_archetype", "")).lower()), manifest[0])
        f = ctx.root / "shared" / "swipe-vault" / ctx.niche / pick["file"]
        ev = (f"advertiser {pick.get('advertiser')}; {pick.get('format_archetype')}; "
              f"{pick.get('signal_tier')}: {pick.get('evidence')}")
        return (f.read_bytes() if f.exists() else None), ev

    async def stage_judge(self, ctx: Ctx) -> str:
        photo = self._product_photo(ctx)
        while True:
            await self._ensure_candidates(ctx)
            pending: dict[str, list[str]] = {}
            for nn, s in sorted(ctx.batch.slots.items()):
                if s["state"] == "open" and s["judged_round"] < s["round"]:
                    pending.setdefault(s["concept"], []).append(nn)
            if not pending:
                break
            await asyncio.gather(*(self._judge_concept(ctx, c, nns, photo) for c, nns in pending.items()))
            ctx.batch.save()
        shipped = sum(1 for s in ctx.batch.slots.values() if s["state"] == "shipped")
        escalated = sorted(nn for nn, s in ctx.batch.slots.items() if s["state"] == "escalated")
        if not shipped:
            raise GateBlocked("no creative passed QA; escalate to the human (see qa-log.md)")
        return f"{shipped} creatives shipped" + (f", {len(escalated)} escalated to the human: {escalated}" if escalated else "")

    async def _judge_concept(self, ctx: Ctx, cnum: str, nns: list[str], photo: Path) -> None:
        row = ctx.batch.concepts[cnum]
        card = persona_card_for(self._research_ev(ctx)["persona_cards"], col(row, "persona"))
        images: list[tuple[str, bytes]] = []
        labels: dict[str, dict[str, Path]] = {}
        for nn in nns:
            cands = candidates(self._round_dir(ctx, nn, ctx.batch.slots[nn]["round"]))
            labels[nn] = {c.stem: c for c in cands}
            images += [(f"slot {nn} / {c.stem}", c.read_bytes()) for c in cands]
        images.append(("REAL PRODUCT PHOTOGRAPH", photo.read_bytes()))
        ex_bytes, ex_ev = self._exemplar(ctx, col(row, "format"))
        if ex_bytes:
            images.append(("COMPETITOR EXEMPLAR", ex_bytes))
        # Isolation: images + persona card + brand rules + exemplar + LP promise. No brief, ever.
        evidence = {"persona_card": card, "brand_rules": ctx.brand_rules,
                    "landing_page_promise": ctx.profile["landing_page_promise"],
                    "exemplar_evidence": ex_ev}
        res = await self.call(self.seat(CreativeDirectorB).judge_and_qa, evidence, images)
        verdicts, _ = extract_json(res.output_text)
        (ctx.batch.dir / "qa-raw" / f"{cnum}_r{max(ctx.batch.slots[n]['round'] for n in nns)}.md"
         ).write_text(res.output_text)
        by = {f"{int(m.group()):02d}": v for v in verdicts if (m := re.search(r"\d+", str(v.get("slot", ""))))}
        for nn in nns:
            if nn not in by:
                raise StageError(f"judge returned no verdict for slot {nn}")
            self._apply_verdict(ctx, nn, by[nn], labels[nn])

    def _apply_verdict(self, ctx: Ctx, nn: str, entry: dict, cands: dict[str, Path]) -> None:
        s = ctx.batch.slots[nn]
        ok, why = gates.qa_gate(entry)  # the code, not the prose, decides SHIP
        winner = str(entry.get("winner", "")).split("/")[-1].strip()
        if ok and winner not in cands:
            ok, why = False, f"winner {winner!r} is not one of the candidates {sorted(cands)}"
        scores = entry.get("lever_scores") or []
        log = ctx.batch.dir / "qa-log.md"
        if not log.exists():
            log.write_text("# QA log\n\n| round | slot | winner | 7 levers | total | gate | verdict | fix |\n"
                           "|---|---|---|---|---|---|---|---|\n")
        s["judged_round"] = s["round"]
        outcome = "SHIP" if ok else "REGEN"
        with log.open("a") as fh:
            fh.write(f"| {s['round']} | {nn} | {winner} | {scores} | {sum(scores) if scores else '-'} | "
                     f"{why} | {outcome} | {str(entry.get('fix', '')).replace('|', '/')} |\n")
        if ok:
            src = cands[winner]
            dest = ctx.batch.drive_dir / f"{nn}_{slug(ctx.brand)}_{slug(col(ctx.batch.concepts[s['concept']], 'concept name'))}_1x1{src.suffix.lower()}"
            shutil.copy2(src, dest)
            spec = json.loads((src.parent / "spec.json").read_text()) if (src.parent / "spec.json").exists() else {}
            dest.with_suffix(".json").write_text(json.dumps(
                {**spec, "qa": {"lever_scores": scores, "total": sum(scores), "round": s["round"]}},
                indent=2, ensure_ascii=False))
            s.update(state="shipped", file=dest.name)
        elif s["round"] >= gates.QA_MAX_ROUNDS:
            s.update(state="escalated", blocking_issue=str(entry.get("fix") or why))
        else:
            s.update(round=s["round"] + 1, fix=str(entry.get("fix") or why))

    # ------------------------------------------------------------- Stage 7: copy
    def _shipped(self, ctx: Ctx) -> dict[str, dict]:
        return {nn: s for nn, s in sorted(ctx.batch.slots.items()) if s["state"] == "shipped"}

    def _concept_table(self, ctx: Ctx) -> str:
        rows = []
        for nn, s in self._shipped(ctx).items():
            r = ctx.batch.concepts[s["concept"]]
            rows.append({"creative #": nn, "file_1x1": s["file"], "concept": col(r, "concept name"),
                         "angle": col(r, "angle"), "persona": col(r, "persona"), "hook": col(r, "hook"),
                         "proof device": col(r, "proof")})
        return render_table(rows, list(rows[0]))

    async def stage_copy(self, ctx: Ctx) -> str:
        final = ctx.batch.dir / f"{ctx.batch.id}_COPY-SHEET.csv"
        if final.exists() and not gates.copy_lint(list(csv.DictReader(io.StringIO(final.read_text())))):
            return await self._sweep(ctx, "copy sheet already present and clean; ")
        ev, p = self._research_ev(ctx), ctx.profile
        table = self._concept_table(ctx)
        ad_ev = {"persona_cards": ev["persona_cards"], "customer_language": ev["customer_language"],
                 "market_diagnosis": ev["market_diagnosis"], "concept_table": table,
                 "offer": ctx.offer_text, "landing_page_promise": p["landing_page_promise"],
                 "shipped_copy": self._shipped_copy(ctx), "brand_voice": _or_none(p["brand_voice"], "none"),
                 "batch": ctx.batch.id[1:]}
        writer = self.seat(Copywriter)
        draft = (await self.call(writer.ad, ad_ev)).output_text
        (ctx.batch.dir / "copy-draft.md").write_text(draft)

        def edit_ev(text: str) -> dict:
            # The editor gets the draft, never the writer's self-score or rationale.
            clean = re.split(r"(?im)^.*7-lever self-score.*$", text)[0].strip()
            return {"draft": clean, "persona_cards": ev["persona_cards"],
                    "customer_language": ev["customer_language"], "market_diagnosis": ev["market_diagnosis"],
                    "feeding_creative": f"{table}\n\nLanding-page promise: {p['landing_page_promise']}",
                    "shipped_copy": ad_ev["shipped_copy"], "brand_voice": ad_ev["brand_voice"]}

        editor = self.seat(CopyEditor)
        out = (await self.call(editor.edit, edit_ev(draft))).output_text
        result, prose = extract_json(out)
        log = [f"## Edit pass 1\n{prose}\n"]
        if result.get("bounces"):  # Tier 2: bounce to the writer, max ONE round
            bounces = "\n".join(f"- defect: {b.get('defect')} | evidence line: {b.get('evidence_line')} | "
                                f"source material: {b.get('source_material')}" for b in result["bounces"])
            revised = (await self.call(writer.ad_revision, {**ad_ev, "editor_bounces": bounces,
                                                              "previous_draft": draft})).output_text
            out = (await self.call(editor.edit, edit_ev(revised))).output_text
            result, prose = extract_json(out)
            log.append(f"## Bounce round (one allowed)\n{bounces}\n\n## Edit pass 2\n{prose}\n")
        (ctx.batch.dir / "copy-edit-log.md").write_text("\n".join(log))
        ok, why = gates.copy_gate(result)
        if not ok:
            raise GateBlocked(f"copy does not ship: {why} (see copy-edit-log.md)")
        table_rows = next((t for t in parse_tables(prose) if t and any("file_1x1" in k.lower() for k in t[0])), [])
        if not table_rows:
            raise StageError("edited copy has no copy-sheet table with a file_1x1 column")
        rows = [{c: {k.lower().strip(): v for k, v in r.items()}.get(c.lower(), "") for c in COPY_COLUMNS}
                for r in table_rows]
        issues = gates.copy_lint(rows)
        if issues:
            (ctx.batch.dir / "copy-lint.md").write_text("# Copy lint\n" + "".join(f"- {i}\n" for i in issues))
            raise GateBlocked("copy sheet fails Tier-1 limits: " + "; ".join(issues[:4])
                              + " — fix copy-lint.md items, save the sheet as "
                              f"{final.name} and run again")
        final.write_text(rows_to_csv(rows, COPY_COLUMNS))
        m = re.search(r"(?is)(→\s*Human compliance review.*)$", prose)
        (ctx.batch.dir / f"compliance-review-{ctx.batch.id}.md").write_text(
            (m.group(1) if m else "→ Human compliance review\n\n(editor listed no flagged claims)") + "\n")
        return await self._sweep(ctx, f"{len(rows)} copy rows edited ({why}); ")

    async def _sweep(self, ctx: Ctx, prefix: str) -> str:
        """Batch-level checks (Doc 03). Any FAIL means the batch does not stage."""
        shipped = self._shipped(ctx)
        images = [(s["file"], (ctx.batch.drive_dir / s["file"]).read_bytes()) for s in shipped.values()]
        p = ctx.profile
        res = await self.call(self.seat(CreativeDirectorB).batch_sweep, {
            "n_creatives": len(shipped), "batch": ctx.batch.id[1:], "banned_words":
            ", ".join(p.get("banned_words") or []) or "none listed", "qualifier": p["offer_qualifier"],
            "market": p["market"], "copy_sheet": (ctx.batch.dir / f"{ctx.batch.id}_COPY-SHEET.csv").read_text()},
            images)
        data, prose = extract_json(res.output_text)
        (ctx.batch.dir / "batch-sweep.md").write_text(prose + "\n")
        checks = data.get("checks", [])
        failed = [c for c in checks if str(c.get("result")).upper() == "FAIL" and int(c.get("n", 0)) != 10]
        if len(checks) < 10:
            raise StageError(f"batch sweep reported {len(checks)} of 10 checks")
        if failed:
            raise GateBlocked("batch sweep FAILED — the batch does not stage: " + "; ".join(
                f"#{c['n']} {c.get('detail', '')}" for c in failed[:4]))
        return prefix + "batch sweep passed"

    # -------------------------------------------------------- Stage 8: launch plan
    async def stage_launch(self, ctx: Ctx) -> str:
        p, shipped = ctx.profile, self._shipped(ctx)
        copy_sheet = (ctx.batch.dir / f"{ctx.batch.id}_COPY-SHEET.csv").read_text()
        dest = p["destinations"] or {}
        res = await self.call(self.seat(MediaBuyer).launch_plan, {
            "batch": ctx.batch.id[1:],
            "shipping_files": "\n".join(s["file"] for s in shipped.values()),
            "copy_sheet": copy_sheet,
            "destinations": json.dumps(dest) if dest else f"all angles: {p['destination']}",
            "derived_targets": derived_targets_text(p.get("economics"), p.get("target_cpa")),
            "account_results": self._results_log(ctx),
            "account_state": "unknown — no live account connection; flag it as unknown"})
        ok, why = gates.ad_names_gate(res.output_text, ctx.batch.id, list(shipped))
        out = ctx.brand_dir / "06_briefs-out" / f"launch-plan-{ctx.batch.id}.md"
        out.write_text(res.output_text.strip() + "\n\n> PROPOSAL ONLY — nothing here was applied to any ad account.\n")
        if not ok:
            raise GateBlocked(f"launch plan rejected: {why}")
        for f in (ctx.batch.dir / f"{ctx.batch.id}_COPY-SHEET.csv",
                  ctx.batch.dir / f"compliance-review-{ctx.batch.id}.md"):
            if f.exists():
                shutil.copy2(f, ctx.batch.drive_dir / f.name)
        rows = []
        for cnum in sorted({s["concept"] for s in shipped.values()}):
            r = ctx.batch.concepts[cnum]
            kind = col(r, "70%")
            parent = re.search(r"B\d{2}-\d{2}", kind)
            rows.append({"#": cnum, "CONCEPT": col(r, "concept name"), "ANGLE FAMILY": col(r, "angle"),
                         "PERSONA": col(r, "persona"), "FORMAT ARCHETYPE": col(r, "format"),
                         "HOOK": col(r, "hook"),
                         "TYPE": "new" if gates._is_new(kind) else f"iterate of {parent.group() if parent else kind}"})
        append_ledger(ctx.root, ctx.brand, ctx.batch, rows, len(shipped))
        ctx.batch.status = "staged"
        return f"launch plan written ({why}); ledger updated; PROPOSAL ONLY"
