import os
import time
from datetime import date, timedelta

import pytest

from orchestrator import economics as ec
from orchestrator import gates
from orchestrator.brand_state import Batch, initialize_brand, mark_launched, append_results, append_winning_variables
from orchestrator.parsing import extract_json, parse_tables, split_named_files, unverified_quotes
from orchestrator.errors import StageError


def test_economics_match_the_handbook_worked_example():
    v = 0.33  # AOV $70
    assert round(ec.breakeven_roas(v), 2) == 1.51 and round(ec.target_roas(v), 2) == 2.15
    assert round(ec.max_cpa(70, v), 2) == 32.57
    assert round(ec.breakeven_roas(v, ec.GOOGLE_FEE), 2) == 1.64
    assert round(ec.target_roas(v, ec.GOOGLE_FEE), 2) == 2.34
    assert round(ec.max_cpa(70, v, ec.GOOGLE_FEE), 2) == 29.91
    assert ec.spend_floor(20) == 30 and ec.spend_floor(None) == 30 and ec.spend_floor(40) == 60


def test_missing_economics_say_inputs_needed_and_never_invent():
    text = ec.derived_targets_text({"aov": 70, "cogs_pct": None}, 20)
    assert "inputs needed" in text and "NO net-margin verdict" in text and "target ROAS" not in text


def test_first_batch_passes_flywheel_and_launched_batch_without_readout_blocks(root):
    bd = initialize_brand(root, "Demo")
    assert gates.flywheel_gate(bd) == (True, "brand has never launched a batch")
    b = Batch(bd, "B01", status="staged")
    b.make_dirs(); b.save()
    assert gates.flywheel_gate(bd)[0]  # staged is not launched
    mark_launched(bd, "B01", 120.0)
    ok, why = gates.flywheel_gate(bd)
    assert not ok and "B01" in why and "readout" in why
    append_results(bd, [["2026-09-01", "ad / 1", "B01", "C", "CBO", 50, 2, 25, 2.1, 1.2, 1.1, "SCALE", "x"]])
    assert gates.flywheel_gate(bd)[0]


def test_only_a_staged_batch_can_be_marked_launched(root):
    bd = initialize_brand(root, "Demo")
    b = Batch(bd, "B01", status="in_progress")
    b.make_dirs(); b.save()
    with pytest.raises(ValueError):
        mark_launched(bd, "B01")


def test_research_freshness_needs_real_content_and_age_under_14_days(root):
    bd = initialize_brand(root, "Demo")
    ok, why = gates.research_freshness_gate(bd)
    assert not ok and "missing" in why  # init stubs must not count as fresh
    for f in gates.research_files(bd):
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("# x\n" + "verbatim quote line with real content. " * 5)
    assert gates.research_freshness_gate(bd)[0]
    old = time.time() - 15 * 86400
    os.utime(gates.research_files(bd)[0], (old, old))
    assert not gates.research_freshness_gate(bd)[0]
    os.utime(gates.research_files(bd)[0], None)
    (bd / "07_results" / "invalidate-research.flag").write_text("x")
    assert gates.research_freshness_gate(bd) == (False, "invalidated by the last readout")


def _vault(root, niche="luggage", n=8, run=None):
    lib = gates.pattern_library_path(root, niche)
    lib.parent.mkdir(parents=True, exist_ok=True)
    lib.write_text(f"# Library\nRun date: {run or date.today()} · Ads analysed: 30\n" + "pattern row. " * 30)
    v = root / "shared" / "swipe-vault" / niche
    v.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (v / f"{i:02d}.png").write_bytes(b"x")
    (v / "manifest.json").write_text("[]")


def test_pattern_gate_needs_library_and_vault_under_30_days(root):
    assert not gates.pattern_gate(root, "luggage")[0]
    _vault(root, n=7)
    assert "8-15" in gates.pattern_gate(root, "luggage")[1]
    _vault(root, n=8)
    assert gates.pattern_gate(root, "luggage")[0]
    _vault(root, n=8, run=date.today() - timedelta(days=31))
    ok, why = gates.pattern_gate(root, "luggage")
    assert not ok and "31 days" in why


def test_preflight_routes_run_reuse_and_stops_only_on_the_flywheel(root):
    bd = initialize_brand(root, "Demo")
    items = {i.name: i for i in gates.preflight(root, bd, "luggage")}
    assert items["flywheel gate"].action == "REUSE" and items["research"].action == "RUN"
    assert items["pattern library + swipe vault"].action == "RUN"
    assert gates.blocking(list(items.values())) is None


def _row(i, kind, arch):
    return {"#": str(i), "format archetype": arch, "70% iterate (of what) or 30% new": kind}


def test_portfolio_gate():
    good = [_row(i, "iterate of X" if i <= 7 else "30% new", f"a{i % 5}") for i in range(1, 11)]
    assert gates.portfolio_gate(good)[0]
    assert not gates.portfolio_gate(good[:9])[0]
    assert "archetypes" in gates.portfolio_gate([_row(i, "iterate" if i <= 7 else "30% new", "a") for i in range(1, 11)])[1]
    assert "70/30" in gates.portfolio_gate([_row(i, "iterate", f"a{i % 5}") for i in range(1, 11)])[1]


BRIEF = """# Creative Brief — 01_A_B_v1
## The bet
- Hypothesis: if we show X then Y because T3 evidence.
- Success metric & floor: CPA ≤ 30 at ≥ 45
- Awareness stage / persona: Problem / Fran
## Copy slots for the image
eyebrow: "A"  headline: "B"   proof: "C"   was: "$9"  now: "$5"
"""


def test_brief_gate_no_brief_no_production():
    assert gates.brief_gate(BRIEF)[0]
    assert "hypothesis" in gates.brief_gate(BRIEF.replace("Hypothesis:", "Idea:"))[1]
    assert "copy slot headline" in gates.brief_gate(BRIEF.replace('headline: "B"', ""))[1]
    assert "evidence tier" in gates.brief_gate(BRIEF.replace("T3", "strong"))[1]


@pytest.mark.parametrize("entry,ok", [
    ({"lever_scores": [2, 2, 2, 2, 2, 1, 0], "verdict": "SHIP"}, True),       # 11/14
    ({"lever_scores": [2, 2, 2, 2, 1, 1, 0], "verdict": "SHIP"}, False),      # 10/14 model said SHIP
    ({"lever_scores": [2] * 7, "verdict": "SHIP", "hard_gate_failures": ["product inaccuracy"]}, False),
    ({"lever_scores": [2] * 7, "verdict": "REGEN"}, False),
    ({"lever_scores": [2, 2, 2], "verdict": "SHIP"}, False),
    ({"lever_scores": [3] + [2] * 6, "verdict": "SHIP"}, False),
])
def test_qa_gate_is_decided_by_code_not_prose(entry, ok):
    assert gates.qa_gate(entry)[0] is ok


def test_copy_lint_and_gate():
    rows = [{"#": "1", "headline": "x" * 41, "primary_text": "🔥 hi", "link": ""}]
    text = " ".join(gates.copy_lint(rows))
    assert "headline is 41" in text and "symbol/emoji" in text and "link is empty" in text
    assert gates.copy_lint([{"#": "1", "headline": "ok", "primary_text": "Skip it.", "link": "https://x"}]) == []
    assert not gates.copy_gate({"lever_scores": [2] * 7, "hard_gate_failures": ["invented quote"]})[0]
    assert not gates.copy_gate({"lever_scores": [1] * 7})[0]
    assert gates.copy_gate({"lever_scores": [2] * 7})[0]


def test_ad_names_must_parse():
    assert gates.ad_names_gate("B01 · 01_FitAnxiety\nB01 | 02_Price", "B01", ["01", "02"])[0]
    assert not gates.ad_names_gate("FitAnxiety ad one", "B01", ["01"])[0]


def test_spend_floor_gate_and_enforcement():
    rows = [{"Amount spent": "$12.00"}, {"Amount spent": "$95.50"}]
    assert gates.spend_floor_gate(rows, 20)[0]
    assert not gates.spend_floor_gate([{"Amount spent": "$5"}], 20)[0]
    assert not gates.spend_floor_gate([{"Reach": "9"}], 20)[0]
    ads = [{"ad_name": "a", "spend": 12, "verdict": "KILL", "purchases": 0, "cpa": None, "roas": 0, "ctr": 1, "freq": 1},
           {"ad_name": "b", "spend": 95, "verdict": "SCALE", "purchases": 4, "cpa": 20, "roas": 3, "ctr": 1, "freq": 1},
           {"ad_name": "c", "spend": None, "verdict": "SCALE"}]
    fixed, notes = gates.enforce_spend_floor(ads, 20)
    assert [a["verdict"] for a in fixed] == ["below floor — no verdict", "SCALE"] and len(notes) == 2


def test_winning_variables_need_t1_numbers(root):
    initialize_brand(root, "Demo")
    kept = append_winning_variables(root, "Demo", [
        {"variable_type": "hook", "value": "x", "batch": "B01", "evidence": "$412 spend, CPA $18", "tier": "T1"},
        {"variable_type": "hook", "value": "y", "batch": "B01", "evidence": "felt strong", "tier": "T1"},
        {"variable_type": "hook", "value": "z", "batch": "B01", "evidence": "$9", "tier": "T3"}])
    assert kept == 1


def test_parsing_helpers():
    data, prose = extract_json('text\n```json\n{"a": 1}\n```\n')
    assert data == {"a": 1} and prose == "text"
    with pytest.raises(StageError):
        extract_json("no block")
    files = split_named_files("# customer-language.md\nAAA\n# market-diagnosis.md\nBBB", ["customer-language.md", "market-diagnosis.md"])
    assert files == {"customer-language.md": "AAA", "market-diagnosis.md": "BBB"}
    assert parse_tables("| a | b |\n|---|---|\n| 1 | 2 |\n")[0] == [{"a": "1", "b": "2"}]
    bad, total = unverified_quotes('- "I love it so much really"\n- "invented line nobody said"', "I love it so much, really!")
    assert (bad, total) == (["invented line nobody said"], 2)


REAL_BRIEF = BRIEF.split("## Copy slots")[0] + """## Copy slots for the image

```
eyebrow:   "Cheaper than one checked bag."
headline:  "No more bag fees."
proof:     [inside amber disc] "~~$65 bag fee~~ → $59"
was:       [struck through inside disc] "$65 bag fee"
now:       [dominant inside disc] "$59"
```

---

## Compliance notes
- **"No more bag fees"** — superlative-adjacent claim.
"""


def test_copy_slots_parse_the_layout_a_real_model_produced():
    """Regression from the live run: one slot per line in a code fence, with [annotations]."""
    slots = gates.copy_slots(REAL_BRIEF)
    assert slots == {"eyebrow": "Cheaper than one checked bag.", "headline": "No more bag fees.",
                     "proof": "$65 bag fee → $59", "was": "$65 bag fee", "now": "$59"}
    assert gates.brief_gate(REAL_BRIEF.replace("Hypothesis:", "**Hypothesis:**"))[0]
    assert gates.copy_slots(BRIEF)["now"] == "$5"  # the one-line layout still works


def test_proof_and_was_are_optional_but_eyebrow_headline_now_are_not():
    no_proof = REAL_BRIEF.replace('proof:     [inside amber disc] "~~$65 bag fee~~ → $59"', "proof: (none — the headline IS the proof)")
    assert gates.brief_gate(no_proof)[0] and "proof" not in gates.copy_slots(no_proof)
    assert gates.brief_gate(REAL_BRIEF.replace('now:       [dominant inside disc] "$59"', ""))[0]
    assert "copy slot headline" in gates.brief_gate(REAL_BRIEF.replace('headline:  "No more bag fees."', 'headline: ""'))[1]
