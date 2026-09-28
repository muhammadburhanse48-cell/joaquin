"""A scripted stand-in for the Anthropic client: replies per seat, records every request.

Structured tasks (a request carrying output_config) get a JSON object shaped like the task's
schema in agents/schemas.py; plain tasks get markdown, as the real API would return.
"""

from __future__ import annotations

import json
import re
import threading
from contextlib import contextmanager
from types import SimpleNamespace

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
QUOTE_1 = "I have been burned by cheap suitcases that split in half"
QUOTE_2 = "one less thing to think about at the airport"
ARCHETYPES = ["avatar callout", "us-vs-them", "offer card", "editorial lifestyle", "ui screenshot"]
TEARDOWN_FIELDS = ["format archetype", "layout grid", "focal hierarchy", "colour system", "typography",
                   "hook placement", "proof devices", "product presentation", "realism level",
                   "complexity level", "why it likely works", "signal tier"]


def response(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop_reason,
                           usage=SimpleNamespace(input_tokens=1, output_tokens=1))


class StreamingMixin:
    """messages.stream(**kw) as the SDK exposes it: a context manager whose get_final_message()
    returns the complete response. Delegates to create() so subclasses can override one place."""

    @contextmanager
    def stream(self, **kwargs):
        final = self.create(**kwargs)
        yield SimpleNamespace(get_final_message=lambda: final)


class ScriptedClient(StreamingMixin):
    def __init__(self, judge=None, psych=None, editor_bounce=False, analyst_ads=None, mining_quote=QUOTE_1,
                 rendezvous: tuple[str, str] | None = None, rendezvous_timeout: float = 5.0,
                 truncate_judge: set[str] | frozenset = frozenset()):
        """rendezvous: two prompt-substrings. A call whose prompt contains either one blocks on
        a two-party threading.Barrier until the OTHER one also arrives — deterministic proof
        that two calls are genuinely in flight at once (no sleeps, no timing thresholds; if
        they are not concurrent, the lone caller times out and raises BrokenBarrierError)."""
        self.calls: list[dict] = []
        self.messages = self
        self.judge, self.psych = judge, psych
        self.truncate_judge = set(truncate_judge)  # slots whose judge reply is cut off at max_tokens
        self.editor_bounce, self.analyst_ads, self.mining_quote = editor_bounce, analyst_ads, mining_quote
        self._editor_calls = 0
        # create() runs on real OS threads (Stages.call -> asyncio.to_thread) whenever the
        # orchestrator fans calls out concurrently — guard the mutable state.
        self._lock = threading.RLock()
        self.threads_used: set[int] = set()
        self._rendezvous = rendezvous
        self._barrier = threading.Barrier(2, timeout=rendezvous_timeout) if rendezvous else None

    # -- the Anthropic surface -------------------------------------------------
    def create(self, **kwargs):
        content = kwargs["messages"][0]["content"]
        text = content[-1]["text"]
        labels = [b["text"] for b in content if b["type"] == "text" and b["text"].startswith("[")]
        with self._lock:
            self.calls.append(kwargs)
            self.threads_used.add(threading.get_ident())
        if self._barrier is not None and any(needle in text for needle in self._rendezvous):
            self._barrier.wait()  # blocks here, outside the lock, so the other side can arrive
        if "CONTEXT YOU GET" in text and any(lab.startswith(f"[slot {s} /") for s in self.truncate_judge
                                             for lab in labels):
            return response('{"report_md": "Panel scores for slot', stop_reason="max_tokens")
        reply = self.reply(text, labels)
        structured = "output_config" in kwargs
        if structured != isinstance(reply, dict):
            raise AssertionError(f"structured={structured} but the scripted reply is "
                                 f"{type(reply).__name__} for prompt {text[:80]!r}")
        return response(json.dumps(reply) if structured else reply)

    def seen(self, needle: str) -> list[dict]:
        return [c for c in self.calls if needle in c["messages"][0]["content"][-1]["text"]]

    # -- replies ---------------------------------------------------------------
    def reply(self, t: str, labels: list[str]) -> str | dict:
        if "DO THIS\n1. Extract every distinct theme" in t:
            return {"customer_language_md": f"## PAINS\n- \"{self.mining_quote}\"\n— own reviews · 3×\n"
                                            f"- \"{QUOTE_2}\"\n— own reviews · 2×\n",
                    "market_diagnosis_md": "Awareness: Problem-aware (about 60% of cold traffic); sophistication "
                                           "stage 3; angle gap: fee math.\nAvatar: weekend traveller. Dominant "
                                           "emotion: relief.\n"}
        if "Now build the PERSONA CARDS" in t:
            return {"personas": [
                {"name": "Frequent Fran — weekend traveller",
                 "visual_world": "airport lounges, warm tungsten light, soft neutral luggage",
                 "card_md": "- Who: 34-45 [T1]"},
                {"name": "Budget Ben — value hunter", "visual_world": "bright kitchen, receipts",
                 "card_md": "- Who: 25-34 [T3]"}],
                "closing_table_md": "| persona | pain |\n|---|---|\n| Fran | fees |"}
        if "Now build the ANGLE BANK" in t:
            return {"angle_bank_md": '### A01 — "one less thing"\n- Persona: Frequent Fran\n'
                                     "- Evidence: T1 own-account results, verbatim quote counted 3 times\n"
                                     "- Status: Proven\n", "angle_ids": ["A01"]}
        if "VISUAL TEARDOWN" in t:
            nums = re.findall(r"(?m)^image (\d\d)", t)
            return {"rows": [{"image": n, **{f: ("avatar callout" if f == "format archetype" else "thirds")
                                             for f in TEARDOWN_FIELDS}} for n in nums]}
        if "Cluster them into PATTERNS" in t:
            return "## Patterns\n| pattern | freq |\n|---|---|\n" + "| price disc on product hero | 12/16 |\n" * 8
        if "select the 8-15" in t:
            return {"entries": [{"file": f"{i:02d}_avatar_brand{i}.png", "source_ad_id": f"ad{i}",
                                 "source_url": "unknown", "advertiser": f"brand{i}.com",
                                 "format_archetype": "avatar callout", "signal_tier": "T3", "evidence": "94 days",
                                 "why_it_earned_its_slot": "clean hierarchy", "date_added": "2026-09-20"}
                                for i in range(1, 11)],
                    "rejected_md": "- 11: weak signal"}
        if "Propose 10 concepts" in t:
            return self._portfolio()
        if "Expand concept" in t:
            return self._briefs(t)
        if "CONCEPT PORTFOLIO (the 10)" in t:
            nums = re.findall(r"(?m)^\| (\d\d) \|", t)
            verdicts = self.psych or {"02": ("FIX", "lead with the guarantee")}
            return {"review_md": "Verdict table…", "verdicts": [
                {"concept": int(n), "verdict": verdicts.get(n, ("PASS", ""))[0],
                 "fix": verdicts.get(n, ("PASS", ""))[1]} for n in nums]}
        if "CONTEXT YOU GET" in t:
            return self._judge(labels)
        if "BATCH-LEVEL checks" in t:
            return {"sweep_md": "Sweep prose",
                    "checks": [{"n": n, "result": "PASS", "files": [], "detail": ""} for n in range(1, 11)]}
        if "write the copy sheet for batch" in t:
            return {"rows": self._copy_rows(t), "working_md": "COPY DRAFT",
                    "compliance_flags": [], "self_score_md": "14"}
        if "THE DRAFT ---" in t:
            with self._lock:
                self._editor_calls += 1
                bounce = self.editor_bounce and self._editor_calls == 1
            return {"rows": self._copy_rows(t), "edit_report_md": "Edited asset",
                    "lever_scores": [2, 2, 2, 2, 2, 2, 1], "hard_gate_failures": [],
                    "bounces": [{"defect": "no VoC anchor", "evidence_line": "L2",
                                 "source_material": "customer-language.md"}] if bounce else [],
                    "compliance_flags": ["'lifetime' claim"]}
        if "turn shipped batch" in t:
            files = sorted(set(re.findall(r"(\d\d)_\w+_\w+_1x1", t)))
            return {"plan_md": "## Structure\n…",
                    "ad_names": [{"creative": n, "ad_name": f"B01 · {n}_Concept"} for n in files]}
        if "full readout for" in t:
            return {"readout_md": "Readout prose", **(self.analyst_ads or {
                "ads": [], "winning_variables": [], "learnings": [], "invalidate_research": False})}
        raise AssertionError(f"ScriptedClient has no reply for prompt starting: {t[:120]!r}")

    def _portfolio(self) -> dict:
        concepts = [{"concept_name": f"Concept{i}", "angle_family": f"Family{i}", "persona": "Frequent Fran",
                     "awareness_stage": "Problem", "format_archetype": ARCHETYPES[i % 5], "hook": f"hook {i}",
                     "proof_device": "proof", "mix": "iterate" if i <= 7 else "new",
                     "iterates": "competitor winner" if i <= 7 else "", "evidence_and_tier": "T3 94 days"}
                    for i in range(1, 11)]
        return {"concepts": concepts, "objections_md": "Objections covered: …"}

    def _briefs(self, t: str) -> dict:
        n = int(re.search(r"Expand concept (\d+)", t).group(1))
        return {"briefs": [{
            "brief_md": f"# Creative Brief — {n:02d}_Brand_Concept{n}_v1\n## The bet\n- Hypothesis: if we show "
                        f"Fran X then Y because T3 evidence.\n- Success metric & floor: CPA ≤ 30 at ≥ 45\n"
                        f"- Awareness stage / persona: Problem / Frequent Fran\n## Copy slots for the image\n"
                        f"(model wrote these loosely)\n## Compliance notes\nnone\n",
            "copy_slots": {"eyebrow": "WEEKEND", "headline": "Skip the fee", "proof": "4.8 stars",
                           "was": "$90", "now": "$59"}}]}

    def _judge(self, labels: list[str]) -> dict:
        slots = sorted({m.group(1) for lab in labels if (m := re.match(r"\[slot (\d+) /", lab))})
        out = []
        for s in slots:
            spec = (self.judge or {}).get(s, {})
            if isinstance(spec, list):  # one entry per round; the last repeats
                spec = spec.pop(0) if len(spec) > 1 else spec[0]
            out.append({"slot": spec.get("slot", s), "winner": spec.get("winner", "c1"), "verdict": spec.get("verdict", "SHIP"),
                        "lever_scores": spec.get("scores", [2, 2, 2, 2, 2, 1, 2]),
                        "hard_gate_failures": spec.get("hard", []), "fix": spec.get("fix", ""),
                        "fix_type": "regenerate" if spec.get("fix") else ""})
        return {"report_md": "Panel scores…", "verdicts": out}

    def _copy_rows(self, t: str) -> list[dict]:
        files = sorted(set(re.findall(r"\d\d_\w+_\w+_1x1\.png", t)))
        return [{"number": f[:2], "concept": f"C{f[:2]}", "angle": "A", "persona": "Fran", "file_1x1": f,
                 "on_image": "Skip the fee", "primary_text": "Skip the fee. See more inside.",
                 "headline": "Skip the fee", "cta": "Shop Now", "link": "https://x.test"} for f in files]


class FakeImageSource:
    """Stands in for nano_banana_pro: writes candidates and records the product reference used."""

    def __init__(self):
        self.requests = []
        self._lock = threading.RLock()  # generate() runs on real threads under concurrent fan-out
        self.threads_used: set[int] = set()

    def generate(self, prompt, product_photo, n, out_dir):
        with self._lock:
            self.requests.append((prompt, product_photo))
            self.threads_used.add(threading.get_ident())
        out_dir.mkdir(parents=True, exist_ok=True)
        return [(out_dir / f"c{i}.png").write_bytes(PNG) or out_dir / f"c{i}.png" for i in range(1, n + 1)]
