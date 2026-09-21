import json
from datetime import date, timedelta

import pytest

from orchestrator.brand_state import initialize_brand
from tests.fakes import PNG, QUOTE_1, QUOTE_2

PROFILE = {
    "niche": "luggage", "product": "Hardshell carry-on, $59, free delivery", "market": "US",
    "offer": "$59 (was $90)", "offer_qualifier": "with free 30-day returns",
    "landing_page_promise": "Carry-on that beats airline fees, $59", "buyer_guess": "weekend travellers (a guess)",
    "product_noun": "suitcase", "product_features": "matte navy shell, brass zips, black handle",
    "niche_tone": "premium, restrained", "palette": {"ground": "#F7F3EC", "accent": "#1F3A5F", "contrast": "#111111"},
    "destination": "https://x.test", "banned_words": ["cheap"], "target_cpa": 20.0,
    "economics": {"aov": 70, "cogs_pct": 25, "payment_fee_pct": 3, "shipping_pct": 5},
    "variants_per_concept": 1, "candidates_per_slot": 3,
}


@pytest.fixture
def root(tmp_path):
    return tmp_path


@pytest.fixture
def brand(root):
    """A ready brand: profile, product photo, raw research sources, 16 competitor images."""
    bd = initialize_brand(root, "Acme")
    (bd / "brand.json").write_text(json.dumps(PROFILE))
    (bd / "_product-assets" / "front.png").write_bytes(PNG)
    src = bd / "03_research" / "source"
    src.mkdir(parents=True, exist_ok=True)
    (src / "own-reviews.md").write_text(f"Review: \"{QUOTE_1}\"\nReview: \"{QUOTE_2}\"\n" * 3)
    (src / "competitor-reviews.md").write_text("Review: \"the zips feel solid and the shell is light\"\n")
    inc = root / "shared" / "swipe-vault" / "luggage" / "incoming"
    inc.mkdir(parents=True)
    lines = []
    for i in range(1, 17):
        (inc / f"{i:02d}.png").write_bytes(PNG)
        lines.append(f"image {i:02d} — advertiser: brand{i % 9}.com · US: 94 days running, 6 variants")
    (inc / "evidence.md").write_text("\n".join(lines) + "\n")
    return bd
