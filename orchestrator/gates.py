"""Blocking preflight gates for a brand cycle."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def _fresh(path: Path, max_days: int) -> bool:
    if not path.exists():
        return False
    age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
    return age <= max_days * 86400


def flywheel_gate(brand_dir: Path) -> tuple[bool, str]:
    results = brand_dir / "07_results" / "results-log.md"
    if not results.exists() or not results.read_text().strip().removeprefix("# Results log").strip():
        return True, "brand has never launched a batch"
    text = results.read_text().lower()
    if "spend" in text and "readout" not in text:
        return False, "previous spend is logged without a written readout"
    return True, "previous batch has a readout"


def research_freshness_gate(brand_dir: Path) -> tuple[bool, str]:
    research = brand_dir / "03_research"
    files = [research / name for name in ("customer-language.md", "persona-cards.md", "market-diagnosis.md")]
    if not any(path.exists() for path in files):
        return True, "research has never run; schedule research"
    if all(_fresh(path, 14) for path in files):
        return True, "research files are fresh"
    return False, "research files must all be less than 14 days old"


def pattern_gate(root: Path, niche: str) -> tuple[bool, str]:
    pattern = root / "shared" / "visual-pattern-library" / f"{niche}.md"
    vault = root / "shared" / "swipe-vault" / niche
    if _fresh(pattern, 30) and vault.exists() and any(vault.iterdir()):
        return True, "pattern library and swipe vault are fresh"
    return False, "pattern library and matching swipe vault must be under 30 days old"


def preflight(root: Path, brand_dir: Path, niche: str) -> dict[str, tuple[bool, str]]:
    return {
        "flywheel": flywheel_gate(brand_dir),
        "research": research_freshness_gate(brand_dir),
        "patterns": pattern_gate(root, niche),
    }


def render_plan(checks: dict[str, tuple[bool, str]]) -> str:
    lines = ["Preflight plan"]
    for name, (passed, reason) in checks.items():
        action = "RUN" if passed else "BLOCK"
        lines.append(f"{action:5} {name}: {reason}")
    return "\n".join(lines)