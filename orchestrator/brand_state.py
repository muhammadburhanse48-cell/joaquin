"""Per-brand and shared state: the folder tree, brand profile, batch state, protected files.

THE FOUR FILES THAT MATTER MOST (Doc 00 §7) — if any orchestration corner gets cut under
time pressure, these four must not be it:
    results-log.md        one row per ad per readout — THE flywheel file
    creative-ledger.md    every batch + concept ever shipped; never repeat
    customer-language.md  the word bank every hook and headline is drawn from
    winning-variables.md  proven hooks/angles/formats, with T1 evidence
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .errors import AwaitingInput

BRAND_DIRS = (
    "01_account-audit",
    "02_landing-page/advertorials",
    "03_research/source",
    "04_angles-scripts",
    "05_creatives",
    "06_briefs-out/video",
    "07_results/exports",
    "_product-assets",
)

RESULTS_COLUMNS = ["date", "ad name / id", "batch", "concept", "campaign type", "spend", "purch",
                   "CPA", "ROAS", "CTR", "freq", "verdict", "action taken"]
WINNING_COLUMNS = ["VARIABLE TYPE", "VALUE", "BATCH", "EVIDENCE", "TIER", "DATE", "STATUS", "BRAND"]
LEDGER_COLUMNS = ["#", "CONCEPT", "ANGLE FAMILY", "PERSONA", "FORMAT ARCHETYPE", "HOOK", "TYPE"]
RADAR_COLUMNS = ["FORMAT ARCHETYPE", "NICHE", "EVIDENCE (TIER)", "STATUS", "TRIED?"]
# Doc 06 names angle-performance.md ("aggregate per angle family") but gives no columns;
# this schema is ours.
ANGLE_COLUMNS = ["angle family", "ads", "spend", "purch", "CPA", "ROAS", "verdicts"]


def _table_header(columns: list[str]) -> str:
    return "| " + " | ".join(columns) + " |\n|" + "|".join("---" for _ in columns) + "|\n"


BRAND_FILES = {
    "07_results/results-log.md": "# Results log\n\n" + _table_header(RESULTS_COLUMNS),
    "07_results/angle-performance.md": "# Angle performance\n\n" + _table_header(ANGLE_COLUMNS),
}
SHARED_FILES = {
    "creative-ledger.md": "# Creative ledger\n\n",
    "winning-variables.md": "# Winning variables\n\n" + _table_header(WINNING_COLUMNS),
    "creative-learnings.md": "# Creative learnings\n\n",
    "opportunity-backlog.md": "# Opportunity backlog\n\n",
    "format-radar.md": "# Format radar\n\n" + _table_header(RADAR_COLUMNS),
}

PROFILE_REQUIRED = {
    "niche": "slug used for the pattern library and swipe vault, e.g. luggage",
    "product": "one line: what it is, what it costs, what the offer is",
    "market": "country/countries",
    "offer": "exact numbers of the offer",
    "offer_qualifier": "the qualifier every 'free' / '$0' must carry",
    "landing_page_promise": "the promise the landing page can cash within one scroll",
    "buyer_guess": "your current guess at who buys it (labelled a guess)",
    "product_noun": "e.g. suitcase",
    "product_features": "artwork, colourway, shape, handles, hardware, stitching, finish",
    "niche_tone": "e.g. premium, restrained, editorial",
    "palette": {"ground": "#hex", "accent": "#hex", "contrast": "#hex"},
    "destination": "default landing-page URL",
}
PROFILE_OPTIONAL = {
    "banned_words": [],
    "brand_voice": "none",
    "background": "a soft vertical gradient from #F7F3EC to #E8DFD2, with a single large tonal arc behind the product",
    "target_cpa": None,
    "economics": {"aov": None, "cogs_pct": None, "payment_fee_pct": None, "shipping_pct": None},
    "destinations": {},
    "variants_per_concept": 3,
    "candidates_per_slot": 3,
}


def slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", name.title()) or "Concept"


def _write_if_empty(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        path.write_text(content)


def initialize_brand(root: Path, brand_name: str) -> Path:
    """One function call per new client brand: the tree, the protected files, a profile stub."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", brand_name):
        raise ValueError(f"brand name {brand_name!r}: use letters, digits, - and _ only")
    brand_dir = Path(root) / "brands" / brand_name
    for relative in BRAND_DIRS:
        (brand_dir / relative).mkdir(parents=True, exist_ok=True)
    for relative, content in BRAND_FILES.items():
        _write_if_empty(brand_dir / relative, content)
    shared = Path(root) / "shared"
    for sub in ("visual-pattern-library", "swipe-vault"):
        (shared / sub).mkdir(parents=True, exist_ok=True)
    for filename, content in SHARED_FILES.items():
        _write_if_empty(shared / filename, content)
    profile = brand_dir / "brand.json"
    if not profile.exists():
        stub = {**PROFILE_REQUIRED, **PROFILE_OPTIONAL}
        profile.write_text(json.dumps(stub, indent=2, ensure_ascii=False) + "\n")
    return brand_dir


# ------------------------------------------------------------------------------ profile
def load_profile(brand_dir: Path) -> dict:
    """Load brand.json and fail loudly, listing every missing field."""
    path = brand_dir / "brand.json"
    if not path.exists():
        raise AwaitingInput(f"{path} is missing; initialize the brand first")
    data = json.loads(path.read_text())
    missing = []
    for key, hint in PROFILE_REQUIRED.items():
        value = data.get(key)
        if isinstance(hint, dict):
            if not isinstance(value, dict) or not all(
                re.fullmatch(r"#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})", str(value.get(k, "")))
                for k in hint
            ):
                missing.append(f"{key} (three #hex colours: {', '.join(hint)})")
        elif not str(value or "").strip() or str(value) == hint:
            missing.append(f"{key} ({hint})")
    if missing:
        raise AwaitingInput(f"fill these fields in {path}: " + "; ".join(missing))
    return {**PROFILE_OPTIONAL, **data}


def read(path: Path, default: str = "") -> str:
    return path.read_text().strip() if path.exists() else default


def has_content(path: Path, min_chars: int = 80) -> bool:
    """A file with real content, not just the heading/table header init wrote."""
    if not path.exists():
        return False
    body = "\n".join(
        ln for ln in path.read_text().splitlines()
        if ln.strip() and not ln.lstrip().startswith("#") and not re.fullmatch(r"[|\-: ]+", ln.strip())
    )
    return len(body) >= min_chars


# -------------------------------------------------------------------------------- batches
@dataclass
class Batch:
    """Batch state, persisted to 05_creatives/B<NN>/batch.json so a run can resume."""

    brand_dir: Path
    id: str  # "B01"
    status: str = "in_progress"  # in_progress | awaiting_input | blocked | staged | launched
    completed: list[str] = field(default_factory=list)
    concepts: dict = field(default_factory=dict)  # "01" -> concept row
    excluded: dict = field(default_factory=dict)  # concept no -> reason (psych SWAP)
    slots: dict = field(default_factory=dict)  # "01" -> {concept, variant, round, state, ...}
    launched_on: str | None = None
    launched_spend: float | None = None

    @property
    def dir(self) -> Path:
        return self.brand_dir / "05_creatives" / self.id

    @property
    def drive_dir(self) -> Path:
        return self.brand_dir / "05_creatives" / f"{self.id}_for_drive"

    @property
    def state_file(self) -> Path:
        return self.dir / "batch.json"

    def make_dirs(self) -> None:
        for sub in ("briefs", "prompts", "candidates", "qa-raw"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)
        self.drive_dir.mkdir(parents=True, exist_ok=True)
        (self.brand_dir / "06_briefs-out" / "video" / self.id).mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        data = {k: v for k, v in self.__dict__.items() if k != "brand_dir"}
        self.state_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    @classmethod
    def load(cls, brand_dir: Path, batch_id: str) -> "Batch":
        data = json.loads((brand_dir / "05_creatives" / batch_id / "batch.json").read_text())
        return cls(brand_dir=brand_dir, **data)


def batch_ids(brand_dir: Path) -> list[str]:
    root = brand_dir / "05_creatives"
    return sorted(p.name for p in root.glob("B[0-9][0-9]") if (p / "batch.json").exists())


def open_or_new_batch(brand_dir: Path) -> Batch:
    """Resume the latest unfinished batch, else start the next B<NN>."""
    ids = batch_ids(brand_dir)
    if ids:
        latest = Batch.load(brand_dir, ids[-1])
        if latest.status in ("in_progress", "awaiting_input", "blocked"):
            return latest
        new_id = f"B{int(ids[-1][1:]) + 1:02d}"
    else:
        new_id = "B01"
    batch = Batch(brand_dir=brand_dir, id=new_id)
    batch.make_dirs()
    batch.save()
    return batch


def mark_launched(brand_dir: Path, batch_id: str, spend: float | None = None) -> Batch:
    """Record that a staged batch went live. From here the flywheel gate applies."""
    batch = Batch.load(brand_dir, batch_id)
    if batch.status not in ("staged", "launched"):
        raise ValueError(f"{batch_id} is {batch.status}; only a staged batch can be launched")
    batch.status, batch.launched_on = "launched", date.today().isoformat()
    if spend is not None:
        batch.launched_spend = spend
    batch.save()
    return batch


# ------------------------------------------------------------------------ protected files
def append_ledger(root: Path, brand: str, batch: Batch, rows: list[dict], n_files: int) -> None:
    """Doc 03: '## <Brand> B07 — date — 10 concepts / 30 files', then the concept rows."""
    from .parsing import render_table

    path = Path(root) / "shared" / "creative-ledger.md"
    text = path.read_text() if path.exists() else SHARED_FILES["creative-ledger.md"]
    header = f"## {brand} {batch.id} — {date.today().isoformat()} — {len(rows)} concepts / {n_files} files"
    if header in text:  # idempotent on resume
        return
    hooks = "; ".join(r["HOOK"] for r in rows if r.get("HOOK"))
    block = (
        f"\n{header}\n\n{render_table(rows, LEDGER_COLUMNS)}\n\n"
        f"Don't-repeat additions: {hooks}\nRetired this batch: none\n"
    )
    path.write_text(text.rstrip("\n") + "\n" + block)


def append_results(brand_dir: Path, rows: list[list[str]]) -> None:
    path = brand_dir / "07_results" / "results-log.md"
    with path.open("a") as fh:
        for row in rows:
            fh.write("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in row) + " |\n")


def append_winning_variables(root: Path, brand: str, items: list[dict]) -> int:
    """Promote variables. No numbers, no row: an item without an evidence string is dropped."""
    path = Path(root) / "shared" / "winning-variables.md"
    kept = 0
    with path.open("a") as fh:
        for it in items:
            evidence = str(it.get("evidence", ""))
            if not re.search(r"\d", evidence) or str(it.get("tier", "")).upper() != "T1":
                continue
            cells = [it.get("variable_type", ""), it.get("value", ""), it.get("batch", ""), evidence,
                     "T1", it.get("date", date.today().isoformat()), it.get("status", "ACTIVE"), brand]
            fh.write("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in cells) + " |\n")
            kept += 1
    return kept


def append_learnings(root: Path, brand: str, learnings: list[str]) -> None:
    path = Path(root) / "shared" / "creative-learnings.md"
    with path.open("a") as fh:
        for item in learnings:
            if re.search(r"\d", item):  # principles carry numbers or they are not recorded
                fh.write(f"- [{brand} · {date.today().isoformat()}] {item}\n")


def account_report_path(brand_dir: Path, when: date | None = None) -> Path:
    return brand_dir / "01_account-audit" / f"account-report-{(when or date.today()).isoformat()}.md"


def latest_account_report(brand_dir: Path) -> Path | None:
    reports = sorted((brand_dir / "01_account-audit").glob("account-report-*.md"))
    return reports[-1] if reports else None
