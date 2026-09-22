"""Phase 1: parallel execution.

1a — the pattern-mining teardown loop fans out independent batches concurrently
     (Stages._teardown_batch / stage_patterns). Must never change what each batch's call
     sees, and row order must survive regardless of which batch finishes first.
1b — Stage 1 (research) and Stage 2 (pattern_mining) run in the same wave (loop.WAVES),
     since they read/write disjoint inputs. Checkpointing, exception precedence and the
     reported message must match what strictly sequential execution would have produced.
"""

import asyncio
import json
import re

import pytest

from orchestrator.brand_state import Batch, initialize_brand
from orchestrator.errors import AwaitingInput, GateBlocked
from orchestrator.loop import LABELS, PREREQS, STAGES, WAVES, Pipeline, _waves
from tests.fakes import PNG, FakeImageSource, QUOTE_1, QUOTE_2, ScriptedClient

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


def _brand_with_n_images(root, n: int):
    """Like conftest's `brand` fixture, but with `n` competitor images — enough to force
    multiple 8-image teardown batches (stage_patterns batches by 8)."""
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
    for i in range(1, n + 1):
        (inc / f"{i:02d}.png").write_bytes(PNG)
        lines.append(f"image {i:02d} — advertiser: brand{i % 9}.com · US: 94 days running, 6 variants")
    (inc / "evidence.md").write_text("\n".join(lines) + "\n")
    return bd


def test_teardown_batches_run_on_more_than_one_thread(root):
    """24 images -> 3 batches of 8. If they ran one at a time on the event loop's own thread
    (no asyncio.to_thread fan-out), every call would land on a single OS thread."""
    _brand_with_n_images(root, 24)
    client = ScriptedClient()
    status, _ = asyncio.run(Pipeline(root, client=client).run("Acme", None)), None

    teardown_calls = client.seen("VISUAL TEARDOWN")
    assert len(teardown_calls) == 3  # one call per 8-image batch, none merged or dropped
    assert len(client.threads_used) > 1, (
        "all seat calls ran on a single thread — the teardown fan-out is not actually concurrent")


def test_teardown_rows_keep_image_order_across_batches(root):
    """asyncio.gather returns results in ARGUMENT order, not completion order — flattening must
    keep image 01..24 in numeric order in the table handed to pattern_mining, regardless of
    which of the 3 concurrent batches' API call happens to come back first."""
    _brand_with_n_images(root, 24)
    client = ScriptedClient()
    asyncio.run(Pipeline(root, client=client).run("Acme", None))

    mining_calls = client.seen("Cluster them into PATTERNS")
    assert len(mining_calls) == 1
    prompt_text = mining_calls[0]["messages"][0]["content"][-1]["text"]
    seen_images = re.findall(r"(?m)^\|\s*(\d{2})\s*\|", prompt_text)
    assert seen_images == [f"{i:02d}" for i in range(1, 25)], (
        "teardown rows are out of image order — asyncio.gather's argument-order guarantee "
        "was broken (e.g. by switching to as_completed or sorting by completion)")


def _run(pipeline, brand="Acme"):
    msgs = []

    async def say(m):
        msgs.append(m)

    return asyncio.run(pipeline.run(brand, say)), msgs


def test_waves_match_the_sequential_order():
    """The DAG is a re-grouping of the same 8 stages, not a different pipeline: flattening
    every wave must reproduce the exact order sequential execution always used."""
    flat = [n for wave in WAVES for n in wave]
    assert flat == STAGES[1:9]
    # every stage that isn't research/pattern_mining still gets its own singleton wave —
    # i.e. stays exactly as sequential as before Phase 1
    for wave in WAVES:
        if wave != ["research", "pattern_mining"]:
            assert len(wave) == 1


def test_waves_rejects_a_cyclic_prereq_table():
    with pytest.raises(ValueError):
        _waves({"a": {"b"}, "b": {"a"}})


def test_research_and_pattern_mining_actually_overlap(root, brand):
    """Deterministic proof of concurrency: research's first call and patterns' LAST call
    (after its own teardown + mining calls) rendezvous on a two-party barrier. Research's
    call cannot proceed until patterns has independently done all of its own work and reached
    that point — if the two stages ran one at a time instead, the lone arrival would time out
    (BrokenBarrierError) instead of the run completing normally."""
    client = ScriptedClient(rendezvous=("DO THIS\n1. Extract every distinct theme", "select the 8-15"))
    status, msgs = _run(Pipeline(root, client=client))
    assert status.state == "awaiting_input" and status.current_stage == "production"
    assert any(m.startswith("Stages 1+2/10 running in parallel") for m in msgs)


def test_earlier_stage_wins_when_both_siblings_fail(root):
    """research (GateBlocked, invented quotes) and pattern_mining (AwaitingInput, too few
    images) fail at the same time. The reported failure must be research's — the lower
    STAGES index — because that is what sequential execution would have reported (research
    always ran first and its raise would have pre-empted patterns entirely)."""
    _brand_with_n_images(root, 8)  # < 15 -> pattern_mining also fails
    client = ScriptedClient(mining_quote="Totally invented customer sentence nobody wrote")
    status, _ = _run(Pipeline(root, client=client))
    assert status.state == "blocked" and status.current_stage == "research"
    assert "quotes" in status.message.lower()
    assert "also:" in status.message and "Pattern mining" in status.message  # the sibling is still reported
    assert not (root / "brands/Acme/03_research/customer-language.md").exists()


def test_successful_sibling_is_checkpointed_when_the_other_fails(root, brand):
    """research fails (AwaitingInput: no product photo isn't it — use missing source files),
    pattern_mining succeeds. The successful sibling must be recorded in batch.completed so a
    resume never re-pays for it, even though the wave as a whole raised."""
    for f in (brand / "03_research/source").glob("*.md"):
        f.unlink()
    client = ScriptedClient()
    status, _ = _run(Pipeline(root, client=client))
    assert status.state == "awaiting_input" and status.current_stage == "research"
    b = Batch.load(brand, "B01")
    assert "pattern_mining" in b.completed and "research" not in b.completed
    teardown_calls_before_resume = len(client.seen("VISUAL TEARDOWN"))

    (brand / "03_research/source/own-reviews.md").write_text(
        f'Review: "{QUOTE_1}"\nReview: "{QUOTE_2}"\n' * 3)
    (brand / "03_research/source/competitor-reviews.md").write_text(
        'Review: "the zips feel solid and the shell is light"\n')
    status, _ = _run(Pipeline(root, client=client))
    assert status.state == "awaiting_input" and status.current_stage == "production"
    assert len(client.seen("VISUAL TEARDOWN")) == teardown_calls_before_resume  # not redone


def test_max_parallel_is_respected(root):
    """The global semaphore in Stages.call bounds concurrency across the whole wave, not just
    within one stage's own fan-out."""
    _brand_with_n_images(root, 24)  # 3 independent teardown calls, competing with research's chain
    client = ScriptedClient()
    p = Pipeline(root, client=client, max_parallel=2)
    _run(p)
    assert p._sem._value == 2  # released back to full capacity, and never exceeded (no assertion error raised)


def test_candidate_generation_runs_concurrently(root, brand):
    """Phase 1c: every open slot's image-generation call is independent of every other slot's
    — they should actually run on more than one OS thread, not one at a time."""
    client = ScriptedClient()
    src = FakeImageSource()
    status, _ = _run(Pipeline(root, client=client, image_source=src, max_parallel_images=4))
    assert status.state == "complete", status.message
    assert len(src.threads_used) > 1, "candidate generation ran on a single thread"
    assert len(src.requests) == 10  # every open slot got its own call, none merged or dropped


def test_ensure_candidates_need_list_is_slot_ordered(root, brand):
    """With the default ManualImageSource every slot raises AwaitingInput — the `need` list
    (and its message) must list slots in ascending order regardless of which slot's generate()
    call is processed first by the concurrent fan-out."""
    client = ScriptedClient()
    status, _ = _run(Pipeline(root, client=client))  # default ManualImageSource
    assert status.state == "awaiting_input" and status.current_stage == "production"
    nns = re.findall(r"candidates/(\d\d)/", status.message)
    assert nns == sorted(nns) and len(nns) == 6  # need[:6] truncation, still in slot order


def test_teardown_evidence_never_leaks_between_batches(root):
    """Each batch's call must only see its own 8 images' evidence lines — not another batch's,
    and not the whole evidence file. Concurrency must not widen what any one call sees."""
    _brand_with_n_images(root, 24)
    client = ScriptedClient()
    asyncio.run(Pipeline(root, client=client).run("Acme", None))

    for call in client.seen("VISUAL TEARDOWN"):
        text = call["messages"][0]["content"][-1]["text"]
        nums = sorted(re.findall(r"(?m)^image (\d{2})", text))
        assert len(nums) <= 8
        labels = [b["text"] for b in call["messages"][0]["content"] if b["type"] == "text"
                 and b["text"].startswith("[image ")]
        assert len(labels) == len(nums)  # exactly its own images attached, none of another batch's


def test_usage_is_accumulated_per_brand_and_written_to_a_batch_file(root, brand):
    """Phase 1d: every seat call's token usage is recorded (Stages._record_output), summed
    per brand, and written to the batch dir once the run stages successfully."""
    client = ScriptedClient()
    p = Pipeline(root, client=client, image_source=FakeImageSource())
    status, _ = _run(p)
    assert status.state == "complete", status.message
    u = p.usage_summary("Acme")
    assert u["calls"] == len(client.calls) and u["calls"] > 20  # every seat call counted, none missed
    assert u["input_tokens"] == u["calls"] and u["output_tokens"] == u["calls"]  # 1 token/call in the fake
    on_disk = json.loads((brand / "05_creatives/B01/usage.json").read_text())
    assert on_disk == u
    assert re.search(r"\d+ calls, [\d,]+ in / [\d,]+ out", status.message)


def test_rate_limit_retry_after_recognises_429_and_ignores_other_errors():
    from orchestrator.stages import _rate_limit_retry_after

    class RateLimitError(Exception):
        status_code = 429

    assert _rate_limit_retry_after(RateLimitError()) == 5.0
    assert _rate_limit_retry_after(ValueError("not a rate limit")) is None


def test_a_rate_limited_call_pauses_other_concurrent_calls(root, monkeypatch):
    """A 429 on one call clears the shared cooldown Event; a sibling call already waiting on
    it must not proceed until the first call's (short, test-scaled) backoff finishes."""
    _brand_with_n_images(root, 8)  # research + patterns' one teardown call, running together
    calls_seen: list[float] = []
    real_sleep = asyncio.sleep

    async def fast_sleep(seconds, *a, **kw):
        calls_seen.append(seconds)
        return await real_sleep(0)  # don't actually wait 5s in a test

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    class FlakyOnce(ScriptedClient):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self._tripped = False

        def create(self, **kwargs):
            content = kwargs["messages"][0]["content"]
            if not self._tripped and "DO THIS\n1. Extract every distinct theme" in content[-1]["text"]:
                self._tripped = True

                class RateLimitError(Exception):
                    status_code = 429
                raise RateLimitError("slow down")
            return super().create(**kwargs)

    client = FlakyOnce()
    with pytest.raises(Exception):
        asyncio.run(Pipeline(root, client=client).run("Acme", None))
    assert 5.0 in calls_seen  # the cooldown backoff actually ran
