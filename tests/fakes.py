"""A scripted stand-in for the Anthropic client: replies per seat, records every request."""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from types import SimpleNamespace

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
QUOTE_1 = "I have been burned by cheap suitcases that split in half"
QUOTE_2 = "one less thing to think about at the airport"
ARCHETYPES = ["avatar callout", "us-vs-them", "offer card", "editorial lifestyle", "ui screenshot"]


def _json(obj) -> str:
    return "\n```json\n" + json.dumps(obj) + "\n```\n"


class ScriptedClient:
    def __init__(self, judge=None, psych=None, editor_bounce=False, analyst_ads=None, mining_quote=QUOTE_1,
                 rendezvous: tuple[str, str] | None = None, rendezvous_timeout: float = 5.0):
        """rendezvous: two prompt-substrings. A call whose prompt contains either one blocks on
        a two-party threading.Barrier until the OTHER one also arrives — deterministic proof
        that two calls are genuinely in flight at once (no sleeps, no timing thresholds; if
        they are not concurrent, the lone caller times out and raises BrokenBarrierError)."""
        self.calls: list[dict] = []
        self.messages = self
        self.judge, self.psych = judge, psych
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
        reply = self.reply(text, labels)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=reply)],
                               usage=SimpleNamespace(input_tokens=1, output_tokens=1))

    def seen(self, needle: str) -> list[dict]:
        return [c for c in self.calls if needle in c["messages"][0]["content"][-1]["text"]]

    # -- replies ---------------------------------------------------------------
    def reply(self, t: str, labels: list[str]) -> str:
        if "DO THIS\n1. Extract every distinct theme" in t:
            return (f"# customer-language.md\n## PAINS\n- \"{self.mining_quote}\"\n— own reviews · 3×\n"
                    f"- \"{QUOTE_2}\"\n— own reviews · 2×\n\n# market-diagnosis.md\nAwareness: Problem-aware (about 60% of cold traffic); sophistication stage 3; angle gap: fee math.\nAvatar: weekend traveller. Dominant emotion: relief.\n")
        if "Now build the PERSONA CARDS" in t:
            return ("## Persona: Frequent Fran — weekend traveller\n- Who: 34-45 [T1]\n"
                    "- Visual world: airport lounges, warm tungsten light, soft neutral luggage\n"
                    "## Persona: Budget Ben — value hunter\n- Visual world: bright kitchen, receipts\n")
        if "Now build the ANGLE BANK" in t:
            return '### A01 — "one less thing"\n- Persona: Frequent Fran\n- Evidence: T1 own-account results, verbatim quote counted 3 times\n- Status: Proven\n'
        if "VISUAL TEARDOWN" in t:
            nums = re.findall(r"(?m)^image (\d\d)", t)
            rows = "\n".join(f"| {n} | avatar callout | thirds |" for n in nums)
            return f"| image | format archetype | layout grid |\n|---|---|---|\n{rows}\n"
        if "Cluster them into PATTERNS" in t:
            return "## Patterns\n| pattern | freq |\n|---|---|\n" + "| price disc on product hero | 12/16 |\n" * 8
        if "select the 8-15" in t:
            return "\n".join(json.dumps({"file": f"{i:02d}_avatar_brand{i}.png", "source_ad_id": f"ad{i}",
                                         "advertiser": f"brand{i}.com", "format_archetype": "avatar callout",
                                         "signal_tier": "T3", "evidence": "94 days"}) for i in range(1, 11))
        if "Propose 10 concepts" in t:
            return self._portfolio()
        if "Expand concept" in t:
            return self._briefs(t)
        if "CONCEPT PORTFOLIO (the 10)" in t:
            nums = re.findall(r"(?m)^\| (\d\d) \|", t)
            verdicts = self.psych or {"02": ("FIX", "lead with the guarantee")}
            return "Verdict table…\n" + _json([
                {"concept": int(n), "verdict": verdicts.get(n, ("PASS", ""))[0],
                 "fix": verdicts.get(n, ("PASS", ""))[1]} for n in nums])
        if "CONTEXT YOU GET" in t:
            return self._judge(labels)
        if "BATCH-LEVEL checks" in t:
            return "Sweep prose" + _json({"checks": [{"n": n, "result": "PASS", "files": [], "detail": ""}
                                                     for n in range(1, 11)]})
        if "write the copy sheet for batch" in t:
            return "COPY DRAFT\n" + self._copy_table(t) + "\n→ Human compliance review\n- none\n7-lever self-score: 14"
        if "THE DRAFT ---" in t:
            with self._lock:
                self._editor_calls += 1
                bounce = self.editor_bounce and self._editor_calls == 1
            return ("Edited asset\n" + self._copy_table(t) + "\n→ Human compliance review\n- 'lifetime' claim\n"
                    + _json({"lever_scores": [2, 2, 2, 2, 2, 2, 1], "hard_gate_failures": [],
                             "bounces": [{"defect": "no VoC anchor", "evidence_line": "L2",
                                          "source_material": "customer-language.md"}] if bounce else []}))
        if "turn shipped batch" in t:
            files = re.findall(r"(\d\d)_\w+_\w+_1x1", t)
            return "## Ad names\n" + "\n".join(f"- B01 · {n}_Concept" for n in sorted(set(files)))
        if "full readout for" in t:
            return "Readout prose" + _json(self.analyst_ads or {"ads": [], "winning_variables": [],
                                                                "learnings": [], "invalidate_research": False})
        raise AssertionError(f"ScriptedClient has no reply for prompt starting: {t[:120]!r}")

    def _portfolio(self) -> str:
        rows = []
        for i in range(1, 11):
            kind = "iterate of competitor winner" if i <= 7 else "30% new"
            rows.append(f"| {i} | Concept{i} | Family{i} | Frequent Fran | Problem | {ARCHETYPES[i % 5]} | "
                        f"hook {i} | proof | {kind} | T3 94 days |")
        head = ("| # | concept name | angle family | persona | awareness stage | format archetype | "
                "hook (verbatim, ≤5 words) | proof device | 70% iterate (of what) or 30% new | evidence + tier |\n"
                "|---|---|---|---|---|---|---|---|---|---|\n")
        return head + "\n".join(rows) + "\n\nObjections covered: …\n"

    def _briefs(self, t: str) -> str:
        n = int(re.search(r"Expand concept (\d+)", t).group(1))
        return "\n".join(
            f"# Creative Brief — {n:02d}_Brand_Concept{n}_v{k}\n## The bet\n- Hypothesis: if we show Fran X then Y "
            f"because T3 evidence.\n- Success metric & floor: CPA ≤ 30 at ≥ 45\n- Awareness stage / persona: "
            f"Problem / Frequent Fran\n## Copy slots for the image\n"
            f"eyebrow: \"WEEKEND\"  headline: \"Skip the fee\"   proof: \"4.8 stars\"   was: \"$90\"  now: \"$59\"\n"
            f"## Compliance notes\nnone\n" for k in range(1, 2))

    def _judge(self, labels: list[str]) -> str:
        slots = sorted({m.group(1) for lab in labels if (m := re.match(r"\[slot (\d+) /", lab))})
        out = []
        for s in slots:
            spec = (self.judge or {}).get(s, {})
            if isinstance(spec, list):  # one entry per round; the last repeats
                spec = spec.pop(0) if len(spec) > 1 else spec[0]
            out.append({"slot": s, "winner": spec.get("winner", "c1"), "verdict": spec.get("verdict", "SHIP"),
                        "lever_scores": spec.get("scores", [2, 2, 2, 2, 2, 1, 2]),
                        "hard_gate_failures": spec.get("hard", []), "fix": spec.get("fix", ""),
                        "fix_type": "regenerate" if spec.get("fix") else ""})
        return "Panel scores…" + _json(out)

    def _copy_table(self, t: str) -> str:
        files = sorted(set(re.findall(r"\d\d_\w+_\w+_1x1\.png", t)))
        head = "| # | concept | angle | persona | file_1x1 | on_image | primary_text | headline | cta | link |\n|---|---|---|---|---|---|---|---|---|---|\n"
        return head + "\n".join(
            f"| {f[:2]} | C{f[:2]} | A | Fran | {f} | Skip the fee | Skip the fee. See more inside. | Skip the fee | Shop Now | https://x.test |"
            for f in files)


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
