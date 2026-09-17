"""Per-brand and shared state layout."""

from __future__ import annotations

from datetime import date
from pathlib import Path


BRAND_DIRS = (
    "01_account-audit",
    "02_landing-page/advertorials",
    "03_research",
    "04_angles-scripts",
    "05_creatives",
    "06_briefs-out/video",
    "07_results",
    "_product-assets",
)

SHARED_DIRS = ("visual-pattern-library", "swipe-vault")


def initialize_brand(root: Path, brand_name: str) -> Path:
    """Create a new brand tree and the four protected flywheel files."""
    brand_dir = root / "brands" / brand_name
    for relative in BRAND_DIRS:
        (brand_dir / relative).mkdir(parents=True, exist_ok=True)
    (brand_dir / "05_creatives" / "B01_for_drive").mkdir(exist_ok=True)
    (brand_dir / "06_briefs-out" / "video" / "B01").mkdir(parents=True, exist_ok=True)
    (root / "shared" / "visual-pattern-library").mkdir(parents=True, exist_ok=True)
    (root / "shared" / "swipe-vault").mkdir(parents=True, exist_ok=True)
    protected = {
        "07_results/results-log.md": "# Results log\n\n",
        "07_results/angle-performance.md": "# Angle performance\n\n",
        "03_research/customer-language.md": "# Customer language\n\n",
        "03_research/persona-cards.md": "# Persona cards\n\n",
        "03_research/market-diagnosis.md": "# Market diagnosis\n\n",
        "03_research/winning-concepts.md": "# Winning concepts\n\n",
        "04_angles-scripts/angle-bank.md": "# Angle bank\n\n",
    }
    for relative, content in protected.items():
        path = brand_dir / relative
        path.touch(exist_ok=True)
        if path.stat().st_size == 0:
            path.write_text(content)
    for filename, heading in {
        "creative-ledger.md": "# Creative ledger\n\n",
        "winning-variables.md": "# Winning variables\n\n",
        "creative-learnings.md": "# Creative learnings\n\n",
        "opportunity-backlog.md": "# Opportunity backlog\n\n",
        "format-radar.md": "# Format radar\n\n",
    }.items():
        path = root / "shared" / filename
        path.touch(exist_ok=True)
        if path.stat().st_size == 0:
            path.write_text(heading)
    return brand_dir


def account_report_path(brand_dir: Path, when: date | None = None) -> Path:
    report_date = (when or date.today()).isoformat()
    return brand_dir / "01_account-audit" / f"account-report-{report_date}.md"