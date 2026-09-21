"""End-to-end runs of stages 0-9 against a scripted model. No network."""

import asyncio
import csv
import json
import re

import pytest

from orchestrator.brand_state import Batch, mark_launched
from orchestrator.errors import AlreadyRunning
from orchestrator.loop import Pipeline
from tests.fakes import PNG, FakeImageSource, ScriptedClient


def run(pipeline, brand="Acme"):
    msgs = []

    async def say(m):
        msgs.append(m)

    return asyncio.run(pipeline.run(brand, say)), msgs


def drop_candidates(brand_dir, batch_id="B01", n=3):
    b = Batch.load(brand_dir, batch_id)
    for nn, s in b.slots.items():
        if s["state"] == "open":
            d = b.dir / "candidates" / nn / f"r{s['round']}"
            d.mkdir(parents=True, exist_ok=True)
            for i in range(1, n + 1):
                (d / f"c{i}.png").write_bytes(PNG)
    return b


PSYCH = {"02": ("FIX", "lead with the guarantee"), "03": ("SWAP", "swap in the price-anchor concept")}


def test_full_cycle_with_human_supplied_images_resumes_and_stages(root, brand):
    client = ScriptedClient(psych=PSYCH)
    p = Pipeline(root, client=client)  # default ManualImageSource: no generator configured

    status, msgs = run(p)
    assert status.state == "awaiting_input" and status.current_stage == "production"
    assert "Stage 0/10" in msgs[0] and re.search(r"RUN\s+research", msgs[0])
    assert any(m.startswith("Stage 3/10: Concept portfolio") for m in msgs)
    assert any(m.startswith("Stage 4/10: Psych review — 8 PASS / 1 FIX / 1 SWAP") for m in msgs)
    b = Batch.load(brand, "B01")
    assert b.status == "awaiting_input" and "psych_review" in b.completed and b.excluded == {"03": "swap in the price-anchor concept"}
    prompts = sorted((b.dir / "prompts").glob("*.md"))
    assert len(prompts) == 9  # the SWAP concept gets no production
    assert all("front.png" in f.read_text() and "attached reference image" in f.read_text() for f in prompts)
    # files written by every stage so far
    assert "one less thing" in (brand / "03_research/customer-language.md").read_text()
    assert (brand / "03_research/persona-cards.md").exists() and (brand / "04_angles-scripts/angle-bank.md").exists()
    assert (root / "shared/visual-pattern-library/luggage.md").read_text().startswith("# Visual Pattern Library — luggage\nRun date:")
    assert 8 <= len(json.loads((root / "shared/swipe-vault/luggage/manifest.json").read_text())) <= 15
    assert len(list((b.dir / "briefs").glob("*.md"))) == 10

    # a human drops candidates; the same command resumes at production
    drop_candidates(brand)
    status, msgs = run(p)
    assert status.state == "complete", status.message
    assert not any("Stage 1/10" in m or "Stage 3/10" in m for m in msgs)  # finished stages are not redone
    b = Batch.load(brand, "B01")
    assert b.status == "staged"
    shipped = sorted(f.name for f in b.drive_dir.glob("*_1x1.png"))
    assert len(shipped) == 9 and shipped[0].startswith("01_Acme_Concept1_1x1")
    assert len(list(b.drive_dir.glob("*_1x1.json"))) == 9  # sidecar spec next to every image
    rows = list(csv.DictReader((b.dir / "B01_COPY-SHEET.csv").open()))
    assert len(rows) == 9 and list(rows[0]) == ["#", "concept", "angle", "persona", "file_1x1", "on_image", "primary_text", "headline", "cta", "link"]
    assert (b.drive_dir / "B01_COPY-SHEET.csv").exists() and (b.drive_dir / "compliance-review-B01.md").exists()
    plan = (brand / "06_briefs-out/launch-plan-B01.md").read_text()
    assert "B01 · 01_Concept" in plan and "PROPOSAL ONLY" in plan
    ledger = (root / "shared/creative-ledger.md").read_text()
    assert "## Acme B01" in ledger and "9 concepts / 9 files" in ledger and "Don't-repeat additions" in ledger
    assert "| # | CONCEPT | ANGLE FAMILY | PERSONA | FORMAT ARCHETYPE | HOOK | TYPE |" in ledger

    # Law 2, checked on the real request payloads (buildspec step 5), not just the code
    for needle in ("CONCEPT PORTFOLIO (the 10)", "CONTEXT YOU GET", "THE DRAFT ---"):
        seen = client.seen(needle)
        assert seen, needle
        for call in seen:
            blob = json.dumps(call["messages"]) + call["system"]
            assert "Creative Brief" not in blob and "Hypothesis:" not in blob and "Objections covered" not in blob
    # every judge call carries the real product photo and the candidate labels
    for call in client.seen("CONTEXT YOU GET"):
        texts = [b["text"] for b in call["messages"][0]["content"] if b["type"] == "text"]
        assert "[REAL PRODUCT PHOTOGRAPH]" in texts and any(t.startswith("[slot ") for t in texts)
    # the FIX went back to the author once; the SWAP was never briefed again
    assert len(client.seen("THE CRITIC'S NAMED FIX")) == 1
    # every seat call was a single fresh message
    assert all(len(c["messages"]) == 1 for c in client.calls)

    # Law 3: launch it, and the next batch is blocked until a readout is written
    mark_launched(brand, "B01", 300.0)
    status, msgs = run(p)
    assert status.state == "blocked" and "readout" in status.message and re.search(r"STOP\s+flywheel gate", msgs[0])
    assert Batch.load(brand, "B02").status == "blocked"


def test_generated_candidates_regenerate_with_the_judges_fix_then_ship(root, brand):
    client = ScriptedClient(psych={}, judge={"01": [
        {"verdict": "REGEN", "scores": [1, 1, 1, 1, 1, 1, 1], "fix": "Re-bake the hook to 'Skip the fee'"},
        {"verdict": "SHIP"}]})
    src = FakeImageSource()
    status, _ = run(Pipeline(root, client=client, image_source=src))
    assert status.state == "complete", status.message
    b = Batch.load(brand, "B01")
    assert b.slots["01"]["round"] == 2 and b.slots["01"]["state"] == "shipped"
    regen = [req for req in src.requests if "REGENERATION FIX" in req[0]]
    assert len(regen) == 1 and "Skip the fee" in regen[0][0]
    assert all(photo.name == "front.png" for _, photo in src.requests)  # product photo on EVERY call
    log = (b.dir / "qa-log.md").read_text()
    assert "| 1 | 01 |" in log and "| 2 | 01 |" in log and "REGEN" in log


def test_three_failed_rounds_escalate_to_the_human_and_the_batch_carries_on(root, brand):
    client = ScriptedClient(psych={}, judge={"01": [{"verdict": "REGEN", "scores": [2] * 7, "hard": ["product inaccuracy"], "fix": "handle is wrong"}]})
    status, msgs = run(Pipeline(root, client=client, image_source=FakeImageSource()))
    assert status.state == "complete"
    b = Batch.load(brand, "B01")
    assert b.slots["01"]["state"] == "escalated" and b.slots["01"]["round"] == 3
    assert b.slots["01"]["blocking_issue"] == "handle is wrong"
    assert any("escalated to the human: ['01']" in m for m in msgs)
    assert len(list(b.drive_dir.glob("*_1x1.png"))) == 9


def test_scores_below_eleven_never_ship_even_if_the_judge_says_ship(root, brand):
    client = ScriptedClient(psych={}, judge={"04": [{"verdict": "SHIP", "scores": [2, 2, 2, 1, 1, 1, 1]}, {"verdict": "SHIP"}]})
    status, _ = run(Pipeline(root, client=client, image_source=FakeImageSource()))
    b = Batch.load(brand, "B01")
    assert b.slots["04"]["round"] == 2  # 10/14 was bounced back for regeneration by the code gate


def test_invented_quotes_block_research(root, brand):
    client = ScriptedClient(mining_quote="Totally invented customer sentence nobody wrote")
    status, _ = run(Pipeline(root, client=client, image_source=FakeImageSource()))
    assert status.state == "blocked" and "not in the source" in status.message
    assert not (brand / "03_research/customer-language.md").exists()  # invented quotes never reach the word bank
    assert (brand / "03_research/mining-pass-rejected.md").exists()
    assert "Not found" in (brand / "03_research/quote-audit.md").read_text()


def test_copy_bounce_goes_back_to_the_writer_exactly_once(root, brand):
    client = ScriptedClient(psych={}, editor_bounce=True)
    status, _ = run(Pipeline(root, client=client, image_source=FakeImageSource()))
    assert status.state == "complete"
    assert len(client.seen("BOUNCE LOG")) == 1 and len(client.seen("THE DRAFT ---")) == 2
    assert "Bounce round" in (Batch.load(brand, "B01").dir / "copy-edit-log.md").read_text()


def test_incomplete_brand_profile_and_missing_inputs_fail_loudly_without_calling_the_model(root):
    from orchestrator.brand_state import initialize_brand
    initialize_brand(root, "Blank")
    client = ScriptedClient()
    status, _ = run(Pipeline(root, client=client), "Blank")
    assert status.state == "awaiting_input" and "niche" in status.message and "palette" in status.message
    assert client.calls == []


def test_missing_source_material_and_missing_product_photo_ask_the_human(root, brand):
    for f in (brand / "03_research/source").glob("*.md"):
        f.unlink()
    client = ScriptedClient()
    status, _ = run(Pipeline(root, client=client))
    assert status.state == "awaiting_input" and "own-reviews.md" in status.message and client.calls == []


def test_one_run_per_brand_at_a_time(root, brand):
    p = Pipeline(root, client=ScriptedClient())
    p._running.add("Acme")
    with pytest.raises(AlreadyRunning):
        asyncio.run(p.run("Acme"))


def test_readout_enforces_spend_floor_reconciles_and_writes_the_flywheel_files(root, brand):
    client = ScriptedClient(psych={}, analyst_ads={
        "ads": [
            {"date": "2026-09-20", "ad_name": "B01 · 01_Concept1", "ad_id": "1", "batch": "B01", "concept": "Concept1",
             "campaign_type": "CBO", "spend": 95, "purchases": 5, "cpa": 19, "roas": 3.1, "ctr": 1.4, "freq": 1.2,
             "verdict": "SCALE", "action_taken": "promote to cost cap"},
            {"date": "2026-09-20", "ad_name": "B01 · 02_Concept2", "ad_id": "2", "batch": "B01", "concept": "Concept2",
             "campaign_type": "CBO", "spend": 12, "purchases": 0, "cpa": None, "roas": 0, "ctr": 0.4, "freq": 1.1,
             "verdict": "KILL", "action_taken": "hook"}],
        "winning_variables": [{"variable_type": "hook", "value": "Skip the fee", "batch": "B01",
                               "evidence": "$95 spend, CPA $19 vs $20 target", "tier": "T1", "status": "ACTIVE"},
                              {"variable_type": "hook", "value": "vibes", "batch": "B01", "evidence": "felt good", "tier": "T1"}],
        "learnings": ["Fee-math hooks beat lifestyle 2.1x CPA across 2 brands"], "invalidate_research": True})
    p = Pipeline(root, client=client, image_source=FakeImageSource())
    assert run(p)[0].state == "complete"
    mark_launched(brand, "B01", 107.0)
    exports = brand / "07_results/exports"
    for f in ("ads-3d.csv", "ads-7d.csv", "ads-lifetime.csv", "country.csv"):
        (exports / f).write_text("Ad name,Amount spent,Purchases\nB01 · 01_Concept1,$95,5\nB01 · 02_Concept2,$12,0\n")
    status = asyncio.run(p.readout("Acme"))
    assert status.state == "complete", status.message
    log = (brand / "07_results/results-log.md").read_text()
    assert "| SCALE |" in log and "| below floor — no verdict |" in log and "| KILL |" not in log  # $12 < $30 floor
    assert "spend-floor corrections" in status.message
    wv = (root / "shared/winning-variables.md").read_text()
    assert "Skip the fee" in wv and "vibes" not in wv  # no numbers, no row
    assert "Fee-math hooks" in (root / "shared/creative-learnings.md").read_text()
    assert (brand / "07_results/invalidate-research.flag").exists()
    assert list((brand / "07_results").glob("readout-*.md"))
    perf = (brand / "07_results/angle-performance.md").read_text()
    assert "| Family1 | 1 | 95.00 | 5 | 19.00 | 3.10 |" in perf  # concept -> angle family via the batch table
    from orchestrator import gates
    assert gates.flywheel_gate(brand)[0]  # the readout unblocks the next batch
    assert not gates.research_freshness_gate(brand)[0]  # and invalidated research must re-run


def test_readout_is_refused_before_anything_reaches_the_spend_floor(root, brand):
    client = ScriptedClient()
    for f in ("ads-3d.csv", "ads-7d.csv", "ads-lifetime.csv", "country.csv"):
        (brand / "07_results/exports" / f).write_text("Ad name,Amount spent\nB01 · 01_C,$4\n")
    status = asyncio.run(Pipeline(root, client=client).readout("Acme"))
    assert status.state == "blocked" and "spend floor" in status.message and client.calls == []


def test_parsers_accept_the_headings_a_real_model_actually_writes():
    """Regression from the first live run: 'Persona 1:' headings and heading-style 'Visual World'."""
    import re
    from orchestrator.stages import PERSONA_HEADING, persona_card_for, visual_world
    cards = ("# PERSONA CARDS\n## Persona 1: The Fee Pragmatist — *\"pays for itself\"*\n### Who\n34-45\n"
             "### Visual World\nAirport lounges, warm tungsten light.\nNavy shell luggage.\n### Evidence Base\nT4\n"
             "## Persona 2: The Anti-Logo Pragmatist\n### Visual World\nBright kitchen.\n"
             "## FLAGGED CANDIDATE — Persona 3: thin\n")
    assert len(re.findall(rf"(?m)^{PERSONA_HEADING}", cards)) == 2  # the flagged candidate is not a card
    card = persona_card_for(cards, "Fee Pragmatist")
    assert card.startswith("## Persona 1") and "Anti-Logo" not in card
    assert visual_world(card) == "Airport lounges, warm tungsten light. Navy shell luggage."
    assert visual_world("## Persona: X\n- Visual world: airport lounge, warm light\n- Evidence: T1") == "airport lounge, warm light"
