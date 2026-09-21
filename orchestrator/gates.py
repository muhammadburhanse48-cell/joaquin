"""Blocking gates. Every gate returns (passed: bool, reason: str).

A gate that fails halts the stage and reports why (the loop raises GateBlocked). Freshness
gates decide RUN vs REUSE at preflight and are re-checked after the refresh stage runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from .brand_state import batch_ids, has_content, latest_account_report, read, Batch
from .economics import spend_floor
from .imagegen import IMAGE_SUFFIXES
from .parsing import col

RESEARCH_MAX_DAYS = 14
PATTERN_MAX_DAYS = 30
ACCOUNT_MAX_DAYS = 7
QA_PASS_SCORE = 11
QA_MAX_ROUNDS = 3
CONCEPTS_PER_BATCH = 10  # Doc 03 and the client's prompt: "Propose 10 concepts"
Gate = tuple[bool, str]


def _age_days(path: Path) -> float:
    return (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) / 86400


# ------------------------------------------------------------------------- preflight gates
def research_files(brand_dir: Path) -> list[Path]:
    r = brand_dir / "03_research"
    return [r / "customer-language.md", r / "market-diagnosis.md", r / "persona-cards.md",
            brand_dir / "04_angles-scripts" / "angle-bank.md"]


def flywheel_gate(brand_dir: Path) -> Gate:
    """Law 3: no readout, no next batch. Exception: the brand has never launched a batch."""
    launched = [b for b in (Batch.load(brand_dir, i) for i in batch_ids(brand_dir))
                if b.status == "launched"]
    if not launched:
        return True, "brand has never launched a batch"
    log = read(brand_dir / "07_results" / "results-log.md")
    missing = [b.id for b in launched if not re.search(rf"\|\s*{b.id}\s*\|", log)]
    if missing:
        return False, (f"{', '.join(missing)} launched but has no written readout in "
                       "results-log.md — run /readout first (no readout, no next batch)")
    return True, "every launched batch has a written readout"


def research_freshness_gate(brand_dir: Path) -> Gate:
    files = research_files(brand_dir)
    if (brand_dir / "07_results" / "invalidate-research.flag").exists():
        return False, "invalidated by the last readout"
    stale = [f.name for f in files if not has_content(f) or _age_days(f) > RESEARCH_MAX_DAYS]
    if stale:
        return False, f"missing or older than {RESEARCH_MAX_DAYS} days: {', '.join(stale)}"
    return True, f"all research files under {RESEARCH_MAX_DAYS} days old"


def pattern_library_path(root: Path, niche: str) -> Path:
    return Path(root) / "shared" / "visual-pattern-library" / f"{niche}.md"


def pattern_age(root: Path, niche: str) -> float | None:
    """Days since the library's own 'Run date:' header; falls back to file mtime."""
    path = pattern_library_path(root, niche)
    if not has_content(path, 200):
        return None
    m = re.search(r"Run date:\s*(\d{4}-\d{2}-\d{2})", path.read_text())
    if m:
        return (date.today() - date.fromisoformat(m.group(1))).days
    return _age_days(path)


def pattern_gate(root: Path, niche: str) -> Gate:
    """Library AND swipe vault must both exist and be under 30 days old."""
    age = pattern_age(root, niche)
    vault = Path(root) / "shared" / "swipe-vault" / niche
    manifest = vault / "manifest.json"
    if age is None:
        return False, f"visual-pattern-library/{niche}.md is missing"
    if age > PATTERN_MAX_DAYS:
        return False, f"pattern library is {age:.0f} days old (limit {PATTERN_MAX_DAYS})"
    images = [p for p in vault.glob("*") if p.suffix.lower() in IMAGE_SUFFIXES] if vault.exists() else []
    if not manifest.exists() or len(images) < 8:
        return False, f"swipe-vault/{niche} needs manifest.json and 8-15 images (has {len(images)})"
    if _age_days(manifest) > PATTERN_MAX_DAYS:
        return False, f"swipe vault is older than {PATTERN_MAX_DAYS} days"
    return True, f"pattern library {age:.0f}d and swipe vault fresh"


def account_gate(brand_dir: Path) -> Gate:
    report = latest_account_report(brand_dir)
    if report is None:
        return False, "no account report on file"
    if _age_days(report) > ACCOUNT_MAX_DAYS:
        return False, f"{report.name} is older than {ACCOUNT_MAX_DAYS} days"
    return True, f"{report.name} is fresh"


@dataclass
class PlanItem:
    name: str
    action: str  # RUN | REUSE | STOP
    reason: str


def preflight(root: Path, brand_dir: Path, niche: str) -> list[PlanItem]:
    """Stage 0. Flywheel is a STOP gate; the freshness gates route RUN vs REUSE."""
    fly_ok, fly_why = flywheel_gate(brand_dir)
    res_ok, res_why = research_freshness_gate(brand_dir)
    pat_ok, pat_why = pattern_gate(root, niche)
    acc_ok, acc_why = account_gate(brand_dir)
    never_launched = "never launched" in fly_why
    return [
        PlanItem("flywheel gate", "REUSE" if fly_ok else "STOP", fly_why),
        PlanItem("account report", "REUSE" if acc_ok else "RUN", acc_why + (
            "" if acc_ok or never_launched else " — supply a fresh ad-level export")),
        PlanItem("research", "REUSE" if res_ok else "RUN", res_why),
        PlanItem("pattern library + swipe vault", "REUSE" if pat_ok else "RUN", pat_why),
    ]


def render_plan(items: list[PlanItem], brand_dir: Path | None = None, niche: str = "") -> str:
    lines = ["Preflight plan"]
    lines += [f"{i.action:5} {i.name}: {i.reason}" for i in items]
    if brand_dir is not None:
        ledger = read(brand_dir.parents[1] / "shared" / "creative-ledger.md")
        lines.append(f"don't-repeat set: {len(re.findall(r'^## ', ledger, re.M))} batch(es) in the ledger")
    return "\n".join(lines)


def blocking(items: list[PlanItem]) -> PlanItem | None:
    return next((i for i in items if i.action == "STOP"), None)


# ------------------------------------------------------------------------------ stage gates
def portfolio_gate(rows: list[dict], expected: int = CONCEPTS_PER_BATCH) -> Gate:
    """Doc 03: 10 concepts, ~70/30, at least 4 distinct format archetypes."""
    if len(rows) != expected:
        return False, f"expected {expected} concepts, got {len(rows)}"
    archetypes = {col(r, "format").lower() for r in rows if col(r, "format")}
    if len(archetypes) < 4:
        return False, f"only {len(archetypes)} distinct format archetypes (need at least 4)"
    new = sum(1 for r in rows if _is_new(col(r, "70%")))
    iterate = len(rows) - new
    lo, hi = round(expected * 0.6), round(expected * 0.8)
    if not lo <= iterate <= hi:
        return False, f"{iterate}/{expected} iterate concepts; the mix must be about 70/30 ({lo}-{hi})"
    return True, f"{len(rows)} concepts, {len(archetypes)} archetypes, {iterate}/{new} iterate/new"


def _is_new(cell: str) -> bool:
    c = cell.lower()
    return ("new" in c or "30" in c) and "iterate" not in c


COPY_SLOTS = ("eyebrow", "headline", "proof", "was", "now")
# A creative can legitimately have no eyebrow, proof badge, old price or offer lockup; the model says so.
REQUIRED_COPY_SLOTS = ("headline",)  # a testimonial card may be headline-only


def brief_gate(brief: str) -> Gate:
    """No brief, no production: hypothesis, success metric, persona, evidence tier, copy slots."""
    checks = {
        "hypothesis": r"Hypothesis:\s*\S",
        "success metric": r"Success metric[^:\n]*:\s*\S",
        "persona": r"persona[^:\n]*:\s*\S",
        "evidence tier": r"\bT[1-4]\b",
    }
    missing = [name for name, pat in checks.items() if not re.search(pat, brief, re.I)]
    slots = copy_slots(brief)
    missing += [f"copy slot {s}" for s in REQUIRED_COPY_SLOTS if not slots.get(s)]
    if missing:
        return False, "brief is missing: " + ", ".join(missing)
    return True, "brief complete"


def copy_slots(brief: str) -> dict[str, str]:
    """eyebrow/headline/proof/was/now from the brief's 'Copy slots' block.

    Real briefs write these several ways: one line, or one per line inside a code fence, with an
    optional [annotation] before the quoted string. Strikethrough markers (~~) are not baked text.
    """
    m = re.search(r"##\s*Copy slots[^\n]*\n(.*?)(?=\n##\s|\Z)", brief, re.S | re.I)
    block = m.group(1) if m else ""
    found = re.findall(r'\b(eyebrow|headline|proof|was|now)\s*:\s*(?:\[[^\]\n]*\]\s*)?["“]([^"”\n]*)["”]',
                       block, re.I)
    return {k.lower(): v.replace("~~", "").strip() for k, v in found}


def qa_gate(entry: dict) -> Gate:
    """CD-B: 7 levers x 0-2, ship at >=11/14 with zero hard-gate failures. Code decides, not prose."""
    scores = entry.get("lever_scores")
    if not (isinstance(scores, list) and len(scores) == 7
            and all(isinstance(s, int) and 0 <= s <= 2 for s in scores)):
        return False, "all 7 lever scores (0-2) must be written out"
    hard = [h for h in entry.get("hard_gate_failures") or [] if str(h).strip()]
    if hard:
        return False, f"hard gate failed: {'; '.join(map(str, hard))}"
    if sum(scores) < QA_PASS_SCORE:
        return False, f"score {sum(scores)}/14 is below {QA_PASS_SCORE}"
    if str(entry.get("verdict", "")).upper() != "SHIP":
        return False, "judge verdict is REGEN"
    return True, f"score {sum(scores)}/14, no hard-gate failures"


def copy_lint(rows: list[dict]) -> list[str]:
    """Objective Tier-1 limits from Doc 04, re-checked after the editor's pass."""
    issues = []
    for r in rows:
        who = f"#{r.get('#', '?')}"
        head, text, link = r.get("headline", ""), r.get("primary_text", ""), r.get("link", "")
        first = re.split(r"<br>|\n", text.strip())[0] if text.strip() else ""
        if len(head) > 40:
            issues.append(f"{who}: headline is {len(head)} chars (max 40)")
        if len(first) > 125:
            issues.append(f"{who}: first line is {len(first)} chars (max 125)")
        if first and not (first[0].isalnum() or first[0] in "\"'“$£€¿¡("):
            issues.append(f"{who}: primary text opens with a symbol/emoji")
        if len(text) > 2200:
            issues.append(f"{who}: primary text exceeds Meta's 2,200 chars")
        if not link.strip():
            issues.append(f"{who}: link is empty (explicit destination required)")
        if re.search(r"100%\s*free|totally free|absolutely free|no cost", text, re.I):
            issues.append(f"{who}: banned free-offer phrasing")
    return issues


def copy_gate(edit: dict) -> Gate:
    scores = edit.get("lever_scores")
    if not (isinstance(scores, list) and len(scores) == 7 and all(isinstance(s, int) for s in scores)):
        return False, "editor did not write all 7 lever scores"
    hard = [h for h in edit.get("hard_gate_failures") or [] if str(h).strip()]
    if hard:
        return False, f"copy hard gate failed: {'; '.join(map(str, hard))}"
    if sum(scores) < QA_PASS_SCORE:
        return False, f"editor score {sum(scores)}/14 is below {QA_PASS_SCORE}"
    return True, f"editor score {sum(scores)}/14"


def ad_names_gate(plan: str, batch_id: str, numbers: list[str]) -> Gate:
    """Every shipped creative NN must appear in an ad name 'B<NN> · <NN>_<Concept>'."""
    pat = re.compile(rf"{batch_id}\s*[·|]\s*(\d{{2}})_[A-Za-z0-9]+")
    found = set(pat.findall(plan))
    missing = [n for n in numbers if n not in found]
    if missing:
        return False, f"unparseable or missing ad names for creatives {missing} (want '{batch_id} · NN_Concept')"
    return True, f"{len(found)} ad names parse"


def spend_floor_gate(rows: list[dict], target_cpa: float | None) -> Gate:
    """Never call the Analyst with data that cannot be checked against the floor."""
    floor = spend_floor(target_cpa)
    if not rows:
        return False, "the ad-level export is empty"
    spends = [_num(next((v for k, v in r.items() if "spend" in k.lower() or "amount spent" in k.lower()), None))
              for r in rows]
    if all(s is None for s in spends):
        return False, "no spend column found in the export — cannot apply the spend floor"
    above = sum(1 for s in spends if s is not None and s >= floor)
    if above == 0:
        return False, f"no creative has reached the spend floor (${floor:.2f}) — readout is not due yet"
    return True, f"{above} of {len(rows)} ads at or above the ${floor:.2f} spend floor"


def _num(value) -> float | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return float(cleaned)
    except ValueError:
        return None


def enforce_spend_floor(ads: list[dict], target_cpa: float | None) -> tuple[list[dict], list[str]]:
    """Post-check the Analyst's rows: no verdict below the floor, no verdict without numbers."""
    floor = spend_floor(target_cpa)
    fixed, notes = [], []
    for ad in ads:
        ad = dict(ad)
        spend = _num(ad.get("spend"))
        verdict = str(ad.get("verdict", ""))
        judged = verdict.lower() not in ("", "below floor — no verdict", "not launched", "no-promote", "watch")
        if spend is None:
            notes.append(f"{ad.get('ad_name')}: no spend figure — row dropped")
            continue
        if spend < floor and judged:
            notes.append(f"{ad.get('ad_name')}: ${spend:.2f} is below the ${floor:.2f} floor — verdict "
                         f"{verdict!r} replaced")
            ad["verdict"], ad["action_taken"] = "below floor — no verdict", f"spend ${spend:.2f} < floor ${floor:.2f}"
        elif judged and not all(ad.get(k) is not None for k in ("purchases", "ctr", "freq")) and (
                ad.get("cpa") is None and ad.get("roas") is None):
            notes.append(f"{ad.get('ad_name')}: verdict {verdict!r} without numbers — replaced")
            ad["verdict"] = "below floor — no verdict"
        fixed.append(ad)
    return fixed, notes

