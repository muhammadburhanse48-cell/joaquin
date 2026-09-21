"""Rebuild agents/prompts/ from the client-supplied prompts_source/ files.

The client's wording is copied verbatim. Only three kinds of mechanical edits are
made, so the chat-style handbook prompts can run as stateless API calls:

1. Fill-in slots (<paste>, <attach>, <brand>, <NN> ...) become named {{slots}}
   that the orchestrator fills from files. Output-schema placeholders such as
   "## Persona: <memorable name>" are left untouched.
2. "Confirm, then wait for the brief" lines are removed. In a one-shot API call
   the model would otherwise just acknowledge and do no work.
3. Each seat's SYSTEM material and TASK material are split into system.md and
   task_*.md instead of being duplicated in both (which sent every prompt twice).

Anything not in the client's sources (gap-fills, machine-readable envelopes,
statelessness preambles) sits under a "GAP-FILL" / "ORCHESTRATION" HTML comment
or an explicitly labelled block so it can be reviewed.

Run:  python scripts/build_prompts.py
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "prompts_source"
OUT = ROOT / "agents" / "prompts"

PASTE = re.compile(r"<(?:paste|attach)[^>]*>")
HEADER = re.compile(
    r"^## (SYSTEM PROMPT|SYSTEM \+ TASK|TASK|TEMPLATE|Reference|Non-negotiable)", re.M
)
ATTACHED = "[attached as image(s) above]"


# --------------------------------------------------------------------------- helpers
def sections(seat: str) -> list[tuple[str, str]]:
    text = (SRC / f"{seat}.md").read_text()
    marks = list(HEADER.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        block = text[m.start():end].strip()
        title, _, body = block.partition("\n")
        out.append((title[3:].strip(), body.strip().rstrip("-").strip()))
    return out


def sec(seat: str, prefix: str) -> str:
    for title, body in sections(seat):
        if title.startswith(prefix):
            return body
    raise KeyError(f"{seat}: no section starting {prefix!r}")


def strip_confirm(text: str) -> str:
    return re.sub(r"\n*Confirm[^\n]*wait for[^\n]*\s*$", "", text).strip()


def slots(text: str, keys: list[str]) -> str:
    """Replace successive <paste…>/<attach…> tokens with {{key}} slots."""
    found = PASTE.findall(text)
    if len(found) != len(keys):
        raise ValueError(f"expected {len(keys)} slots, found {len(found)}: {found}")
    it = iter(keys)
    return PASTE.sub(lambda _m: "{{%s}}" % next(it), text)


def lit(text: str, mapping: dict[str, str]) -> str:
    for old, new in mapping.items():
        if old not in text:
            raise ValueError(f"literal not found: {old!r}")
        text = text.replace(old, new)
    return text


def carve(body: str, start: str, end: str | None) -> tuple[str, str]:
    """Split body into (block from `start` up to `end`, everything else)."""
    i = body.index(start)
    j = body.index(end, i) if end else len(body)
    return body[i:j].strip(), (body[:i] + body[j:]).strip()


def write(seat: str, name: str, text: str, note: str | None = None) -> None:
    path = OUT / seat / name
    path.parent.mkdir(parents=True, exist_ok=True)
    head = f"<!-- {note} -->\n" if note else ""
    path.write_text(head + text.strip() + "\n")


def json_envelope(what: str, shape: str) -> str:
    return (
        "\n\n--- ORCHESTRATION: MACHINE-READABLE " + what + " (required) ---\n"
        "After your normal output above, append ONE fenced ```json block containing exactly:\n"
        + shape
        + "\nThe orchestrator enforces the gates from this block; the prose above stays "
        "authoritative for the human reader."
    )


# ------------------------------------------------------------------------- envelopes
PSYCH_ENVELOPE = json_envelope(
    "VERDICTS",
    '[{"concept": <number>, "verdict": "PASS"|"FIX"|"SWAP", '
    '"fix": "<the named change or swap-in; empty for PASS>"}]  (one object per concept)',
)
JUDGE_ENVELOPE = json_envelope(
    "VERDICTS",
    '[{"slot": "<slot id exactly as labelled on the images>", "winner": "<candidate label>", '
    '"verdict": "SHIP"|"REGEN", "lever_scores": [<7 integers 0-2, in the order the levers are '
    'listed>], "hard_gate_failures": ["<name each failed hard gate, or leave empty>"], '
    '"fix": "<specific evidence-tied fix, empty for SHIP>", '
    '"fix_type": "regenerate"|"recompose"|""}]  (one object per slot)',
)
SWEEP_ENVELOPE = json_envelope(
    "SWEEP RESULT",
    '{"checks": [{"n": <1-10>, "result": "PASS"|"FAIL", "files": ["<named files>"], '
    '"detail": "<one line>"}]}',
)
EDITOR_ENVELOPE = json_envelope(
    "EDIT RESULT",
    '{"lever_scores": [<7 integers 0-2>], "hard_gate_failures": ["<invented quote/review/stat | '
    'message-match break | wrong awareness structure>"], "bounces": [{"defect": "...", '
    '"evidence_line": "...", "source_material": "..."}]}',
)
GATE_ENVELOPE = json_envelope(
    "SCRIPT-GATE RESULT",
    '[{"script": "<id>", "verdict": "SHIP"|"REVISE", "message_match": <0-10>, '
    '"hook_strength": <0-10>, "voc_density": <0-10>, "failed_checks": ["..."], "fix": "..."}]',
)
READOUT_ENVELOPE = json_envelope(
    "READOUT ROWS",
    '{"ads": [{"date": "YYYY-MM-DD", "ad_name": "", "ad_id": "", "batch": "B01|UNMAPPED", '
    '"concept": "", "campaign_type": "", "spend": <number>, "purchases": <number|null>, '
    '"cpa": <number|null>, "roas": <number|null>, "ctr": <number|null>, "freq": <number|null>, '
    '"verdict": "PROMOTE|SCALE|ITERATE|NO-PROMOTE|KILL|FATIGUE|LEARNING|below floor — no verdict|NOT LAUNCHED", '
    '"action_taken": ""}], "winning_variables": [{"variable_type": "", "value": "", "batch": "", '
    '"evidence": "<spend, CPA vs target, CTR — numbers or no row>", "tier": "T1", "date": "YYYY-MM-DD", '
    '"status": "ACTIVE|fatigued|RETIRED"}], "learnings": ["<cross-brand principle with numbers>"], '
    '"invalidate_research": true|false}',
)

EVIDENCE_BASE = """\
--- PERSONA CARDS ---
{{persona_cards}}
--- CUSTOMER LANGUAGE (four buckets + headline phrases) ---
{{customer_language}}
--- MARKET DIAGNOSIS (awareness + sophistication) ---
{{market_diagnosis}}
--- THE CONCEPT TABLE for this batch (concept, angle, persona, hook, proof) ---
{{concept_table}}
--- THE OFFER, exact numbers + required qualifier ---
{{offer}}
--- THE LANDING PAGE PROMISE the click must be congruent with ---
{{landing_page_promise}}
--- ALREADY-SHIPPED COPY (don't repeat hooks) ---
{{shipped_copy}}
--- BRAND VOICE / FORBIDDEN WORDS if you have one ---
{{brand_voice}}"""

STATELESS = (
    "ORCHESTRATION NOTE: this is a fresh, stateless call. There is no earlier chat; every "
    "file you may rely on is pasted below. Do not ask for anything that is not here."
)


# ------------------------------------------------------------------------------ seats
def creative_strategist() -> None:
    s = "creative_strategist"
    write(s, "system.md", strip_confirm(sec(s, "SYSTEM PROMPT")))
    t1 = slots(
        lit(sec(s, "TASK 1"), {
            "<brand>": "{{brand}}",
            "<one line — what it is, what it costs, what the offer is>": "{{product}}",
            "<country/countries>": "{{market}}",
            "<your current guess — say it's a guess>": "{{buyer_guess}}",
        }),
        ["own_reviews", "competitor_reviews", "ad_comments", "forum_threads",
         "competitor_ad_copy", "own_ads"],
    )
    write(s, "task_mining_pass.md", t1)
    pre2 = (
        "EVIDENCE — the files the mining pass wrote, plus the raw material they came from.\n"
        "--- CUSTOMER LANGUAGE ---\n{{customer_language}}\n"
        "--- MARKET DIAGNOSIS ---\n{{market_diagnosis}}\n"
        "--- SOURCE MATERIAL (raw) ---\n{{source_material}}\n\n"
    )
    write(s, "task_persona_cards.md", pre2 + sec(s, "TASK 2"),
          "ORCHESTRATION: the client's 'same chat' continuation is replaced by explicit "
          "evidence so the call stays stateless.")
    pre3 = pre2 + "--- PERSONA CARDS ---\n{{persona_cards}}\n\n"
    t3 = slots(sec(s, "TASK 3"), ["creative_ledger"])
    write(s, "task_angle_bank.md", pre3 + t3,
          "ORCHESTRATION: the client's 'same chat' continuation is replaced by explicit "
          "evidence so the call stays stateless.")


def opportunity_scout() -> None:
    s = "opportunity_scout"
    write(s, "system.md", (
        "You are the Opportunity Scout for a direct-response ecommerce brand on Meta. You hunt "
        "new angles, rising formats and adjacent-niche ideas. You maintain the opportunity "
        "backlog and the format radar.\n\n"
        "YOU REFUSE TO\n- Log an opportunity with no signal behind it.\n"
        "- Describe a US ad as high-spend. US ads show NO spend data; rank them by longevity, "
        "variant count and cross-advertiser repetition only.\n"
        "- Fill a field with a guess when you cannot see the thing clearly."
    ), "GAP-FILL: Doc 02 gives this seat no system prompt. Wrapper written from Doc 00's "
       "seat-table row and Doc 02's own hard rules, as the source file instructs.")
    t1 = sec(s, "TASK 1").replace("<niche>", "{{niche}}")
    t1 = re.sub(r"image 01 —.*?image 02 — \.\.\.", "{{evidence_per_image}}", t1, flags=re.S)
    write(s, "task_visual_teardown.md", t1)
    t2 = slots(lit(sec(s, "TASK 2"), {"<N>": "{{n_rows}}", "<M>": "{{n_advertisers}}"}),
               ["teardown_rows"]).replace("<niche>", "{{niche}}")
    write(s, "task_pattern_mining.md", t2)
    t3 = sec(s, "TASK 3").replace("<N>", "{{n_images}}").replace("<niche>", "{{niche}}")
    write(s, "task_swipe_vault.md",
          "--- TEARDOWN ROWS ---\n{{teardown_rows}}\n--- PATTERN LIBRARY (its 'use first' list) "
          "---\n{{pattern_library}}\n--- EVIDENCE PER IMAGE ---\n{{evidence_per_image}}\n\n" + t3,
          "ORCHESTRATION: evidence block added so the call is stateless.")
    t4 = sec(s, "TASK 4").replace("<N>", "{{n_ads}}").replace("<niche>", "{{niche}}")
    t4 = t4.replace("<given below per ad>", "given below per ad")
    write(s, "task_video_teardown.md",
          t4 + "\n\n--- EVIDENCE PER AD ---\n{{evidence_per_ad}}")


def creative_director_a() -> None:
    s = "creative_director_a"
    body = sec(s, "SYSTEM + TASK")
    task, system = carve(body, "EVIDENCE BASE", None)
    write(s, "system.md", system)
    task = slots(task, ["account_report", "results_log", "persona_cards", "customer_language",
                        "market_diagnosis", "angle_bank", "pattern_library", "format_radar",
                        "creative_ledger"]).replace("B<NN>", "B{{batch}}")
    write(s, "task_concept_portfolio.md", task)
    template = sec(s, "Reference")
    write(s, "brief_template.md", template)
    base = (
        "Expand concept {{concept_number}} of batch B{{batch}} into exactly {{variants}} creative "
        "brief(s): one brief per variant (V1 to V{{variants}}), each using EXACTLY the brief template "
        "below and starting with its own '# Creative Brief' title line. Each variant must differ "
        "from its siblings on at least three variation axes and the variants must be visibly "
        "distinct at thumbnail size. 'Copy slots for the image' must hold the "
        "exact strings that will be baked on the image. Do not write generation prompts.\n\n"
        "--- THE CONCEPT ROW ---\n{{concept_row}}\n"
        "--- BRAND / OFFER / QUALIFIER ---\n{{offer}}\n"
        "--- PERSONA CARDS ---\n{{persona_cards}}\n"
        "--- CUSTOMER LANGUAGE ---\n{{customer_language}}\n"
        "--- ANGLE BANK ---\n{{angle_bank}}\n"
        "--- VISUAL PATTERN LIBRARY ---\n{{pattern_library}}\n"
        "--- SWIPE VAULT MANIFEST ---\n{{swipe_manifest}}\n"
        "--- CREATIVE LEDGER ---\n{{creative_ledger}}\n"
        "--- BRIEF TEMPLATE ---\n" + template
    )
    note = ("GAP-FILL: the client supplies the brief template but no task prompt for expanding "
            "concepts into briefs; this wrapper task is orchestration glue.")
    write(s, "task_write_briefs.md", base, note)
    write(s, "task_revise_briefs.md", base + (
        "\n\n--- THE CRITIC'S NAMED FIX (apply exactly this one change, nothing else) ---\n"
        "{{psych_fix}}\n--- CURRENT BRIEFS FOR THIS CONCEPT ---\n{{current_briefs}}"), note)


def ecommerce_psychologist() -> None:
    s = "ecommerce_psychologist"
    body = sec(s, "SYSTEM + TASK")
    task, system = carve(body, "EVIDENCE — files only", "OUTPUT — one pass")
    write(s, "system.md", system)
    task = slots(task, ["concept_portfolio", "persona_cards", "customer_language",
                        "market_diagnosis", "results_log", "landing_page"])
    write(s, "task_psych_review.md", task + PSYCH_ENVELOPE)


def graphic_designer() -> None:
    s = "graphic_designer"
    write(s, "system.md", sec(s, "Non-negotiable"),
          "Reference for the seat. The Graphic Designer is a template filler (see "
          "task_generation_template.md), not a chat prompt.")
    t = lit(sec(s, "TEMPLATE"), {
        "<EYEBROW>": "{{eyebrow}}", "<HEADLINE>": "{{headline}}", "<PROOF>": "{{proof}}",
        "<WAS>": "{{was}}", "<NOW>": "{{now}}", "<QUALIFIER>": "{{qualifier}}",
        "<product noun>": "{{product_noun}}",
        "<Niche tone: e.g. premium, restrained, editorial>": "{{niche_tone}}",
        "<#hex ground>": "{{palette_ground}}", "<#hex accent>": "{{palette_accent}}",
        "<#hex contrast>": "{{palette_contrast}}",
        "<persona one-liner from the card's visual world>": "{{persona_visual_world}}",
    })
    t = re.sub(r"<name the specific\s+features[^>]*>", "{{product_features}}", t)
    t = re.sub(r"<e\.g\. a soft vertical[^>]*>", "{{background}}", t)
    if "<" in re.sub(r"\{\{[^}]*\}\}", "", t) and re.search(r"<[A-Za-z#]", t):
        raise ValueError("graphic designer template still has unfilled <slots>")
    write(s, "task_generation_template.md", t)


def creative_director_b() -> None:
    s = "creative_director_b"
    body = sec(s, "SYSTEM + TASK")
    ctx, system = carve(body, "CONTEXT YOU GET", "Regeneration protocol")
    write(s, "system.md", system)
    ctx = lit(ctx, {
        "--- THE IMAGES ---   <attach>": f"--- THE IMAGES ---   {ATTACHED}",
        "--- THE REAL PRODUCT PHOTOGRAPH ---   <attach>":
            f"--- THE REAL PRODUCT PHOTOGRAPH ---   {ATTACHED}",
        "<attach + its evidence>": f"{ATTACHED}\n{{{{exemplar_evidence}}}}",
    })
    ctx = slots(ctx, ["persona_card", "brand_rules", "landing_page_promise"])
    write(s, "task_judge_qa.md", ctx + JUDGE_ENVELOPE)
    sweep = sec(s, "TASK")
    sweep = lit(sweep, {
        "<N>": "{{n_creatives}}", "B<NN>": "B{{batch}}", "<qualifier>": "{{qualifier}}",
        "<market>": "{{market}}",
    })
    sweep = slots(sweep, ["banned_words"])
    write(s, "task_batch_sweep.md",
          sweep + "\n\n--- THE COPY SHEET ---\n{{copy_sheet}}" + SWEEP_ENVELOPE,
          "ORCHESTRATION: the client's sweep names 'the copy sheet' but has no slot for it.")


def copywriter() -> None:
    s = "copywriter"
    write(s, "system.md", strip_confirm(sec(s, "SYSTEM PROMPT")))
    ad = slots(sec(s, "TASK — Mode: ad"),
               ["persona_cards", "customer_language", "market_diagnosis", "concept_table",
                "offer", "landing_page_promise", "shipped_copy", "brand_voice"]
               ).replace("B<NN>", "B{{batch}}")
    write(s, "task_ad.md", ad)
    write(s, "task_ad_revision.md", ad + (
        "\n\n--- THE EDITOR'S BOUNCE LOG (fix each item using ONLY the source material it "
        "names; one round, then the editor re-checks) ---\n{{editor_bounces}}\n"
        "--- YOUR PREVIOUS DRAFT ---\n{{previous_draft}}"),
        "ORCHESTRATION: one-round bounce loop from Doc 04 (Copy Editor bounces substantive "
        "misses back once).")
    adv = sec(s, "TASK — Mode: advertorial")
    adv = adv.replace("<angle>", "{{angle}}").replace("<P>", "{{persona}}")
    adv = adv.replace("<paste the same evidence base as the ad task, plus:>",
                      EVIDENCE_BASE + "\nplus:")
    adv = slots(adv, ["feeding_ad", "product_facts", "real_reviews"])
    write(s, "task_advertorial.md", adv)
    ref = sec(s, "Reference")
    pdp = ref[ref.index("### Mode: pdp"):ref.index("### Mode: email")].strip()
    email = ref[ref.index("### Mode: email"):].strip()
    tail = ("\n\nEnd with the \"→ Human compliance review\" list and your 7-lever self-score. "
            "Every quote is a real traceable quote or [EXAMPLE — replace with real].")
    note = ("GAP-FILL: Doc 04 describes this mode but gives no task-prompt template; wrapper "
            "built from the Reference text and the ad/advertorial evidence base.")
    write(s, "task_pdp.md",
          "TASK: write the product-page copy for angle {{angle}}, persona {{persona}}.\n"
          + EVIDENCE_BASE + "\n--- PRODUCT FACTS — the do-not-invent list ---\n{{product_facts}}\n"
          "--- REAL REVIEWS available to quote ---\n{{real_reviews}}\n\n" + pdp + tail, note)
    write(s, "task_email.md",
          "TASK: write the lifecycle email flow copy for angle {{angle}}, persona {{persona}}.\n"
          + EVIDENCE_BASE + "\n--- PRODUCT FACTS — the do-not-invent list ---\n{{product_facts}}\n"
          "--- REAL REVIEWS available to quote ---\n{{real_reviews}}\n\n" + email + tail, note)


def copy_editor() -> None:
    s = "copy_editor"
    body = sec(s, "SYSTEM + TASK")
    ev, system = carve(body, "EVIDENCE", "TIER 1")
    write(s, "system.md", system)
    ev = slots(ev, ["draft", "persona_cards", "customer_language", "market_diagnosis",
                    "feeding_creative", "shipped_copy", "brand_voice"])
    write(s, "task_edit.md", ev + EDITOR_ENVELOPE)


def video_editor() -> None:
    s = "video_editor"
    write(s, "system.md", strip_confirm(sec(s, "SYSTEM PROMPT")) + "\n\n" + sec(s, "Reference"))
    t1 = slots(sec(s, "TASK 1").replace("<N>", "{{n_scripts}}").replace("B<NN>", "B{{batch}}"),
               ["persona_cards", "customer_language", "angle_bank", "video_pattern_library",
                "results_log", "creative_ledger", "available_assets", "offer_and_lp"])
    write(s, "task_scripts.md", t1)
    gate = sec(s, "TASK 2")
    ev, system = carve(gate, "--- THE SCRIPTS ---", "Per script:")
    write(s, "system_script_gate.md", system,
          "Critic seat: the client requires the script gate to be a fresh, isolated call.")
    write(s, "task_script_gate.md",
          slots(ev, ["scripts", "first_3s_rules", "customer_language", "landing_page_promise"])
          + GATE_ENVELOPE)
    t3 = lit(sec(s, "TASK 3"), {
        "--- THE WINNING STATIC --- <attach the image>": f"--- THE WINNING STATIC --- {ATTACHED}",
        "<spend, CPA/ROAS, verdict>": "{{result}}",
        "<the winning variable>": "{{winning_variable}}",
    })
    write(s, "task_motion.md", t3)


def analyst() -> None:
    s = "analyst"
    write(s, "system.md", strip_confirm(sec(s, "SYSTEM PROMPT")) + "\n\n" + sec(s, "Reference"))
    t = lit(sec(s, "TASK"), {"<brand>": "{{brand}}", "<date>": "{{week_of}}"})
    t = slots(t, ["ads_3d", "ads_7d", "ads_lifetime", "country_breakdown", "economics",
                  "creative_ledger", "results_log"])
    write(s, "task_readout.md", t + READOUT_ENVELOPE)


def media_buyer() -> None:
    s = "media_buyer"
    body = sec(s, "SYSTEM + TASK")
    ev, system = carve(body, "--- THE ANALYST'S VERDICT ROWS ---", None)
    write(s, "system.md", strip_confirm(system))
    write(s, "task_scaling_proposal.md",
          slots(ev, ["analyst_rows", "campaign_structure", "derived_targets", "country_table"]))
    lp = slots(sec(s, "TASK").replace("B<NN>", "B{{batch}}"),
               ["shipping_files", "copy_sheet", "destinations", "derived_targets",
                "account_results", "account_state"])
    lp += ("\n\nAD-NAME CONTRACT: write every ad name exactly as `B<NN> · <NN>_<Concept>` "
           "(e.g. `B07 · 03_FitAnxiety`), where <NN> is the concept number from the file name.")
    write(s, "task_launch_plan.md", lp,
          "ORCHESTRATION: the ad-name delimiter is not fixed by the handbook; this contract line "
          "pins it so the readout can parse names.")


def offer_engineer() -> None:
    s = "offer_engineer"
    write(s, "system.md", """\
1. IDENTITY
You are the Offer Engineer for a direct-response ecommerce brand on Meta. You are called only
when the data says the offer — not the creative, not the bid — is the constraint.

2. THE LAW
- Data first. Every recommendation cites numbers from the evidence supplied. If an input is
  missing, say "inputs needed" and stop; never invent economics, prices or results.
- You PROPOSE; a human executes. You never change a live price, bundle, bonus or guarantee.
- You rebuild the offer: price, bundle, bonus, guarantee. You do not rewrite creatives,
  re-judge creative quality, or plan campaign structure (Analyst and Media Buyer own those).
- You are routed here when: CTR is good but CPA is bad; or the 2-ROAS cap (AOV/2) sits under
  what the account is actually buying at; or the Analyst / Ecommerce Psychologist flagged an
  offer-level problem they refuse to fix inside a readout or creative pass.

3. EVIDENCE BASE — read before working
Economics (AOV, COGS %, payment fee %, shipping %), CPA / ROAS data, the route-out flag with
its cited evidence, the current offer.

4. METHOD
Restate the constraint with the numbers that prove it, compute the margin room, then propose
the smallest offer change(s) that restore it, each with the expected effect on CPA/ROAS so the
next readout can confirm or refute it.

5. OUTPUT SPEC
One markdown proposal: constraint + evidence · margin arithmetic (shown) · ranked offer
changes (each with expected effect and what to read afterwards) · what needs human approval.

6. REFUSALS
You refuse to: change live prices without approval · invent numbers · fix creative problems ·
propose an offer change without stating its expected effect on the numbers.""",
          "GAP-FILL (visible flag for the client): the seven handbook docs give the Offer Engineer "
          "NO prompt template. This prompt is DRAFTED from Doc 00's seat table and Doc 06's routing "
          "triggers. Replace it with the client's own prompt if one exists.")
    write(s, "task_offer_rebuild_gap_fill.md", (
        "TASK: rebuild the offer for {{brand}}.\n"
        "--- ECONOMICS: AOV, COGS %, payment fee %, uncovered shipping % ---\n{{economics}}\n"
        "--- CPA / ROAS DATA ---\n{{performance_data}}\n"
        "--- THE ROUTE-OUT FLAG AND ITS EVIDENCE ---\n{{route_out}}\n"
        "--- THE CURRENT OFFER ---\n{{current_offer}}"),
        "GAP-FILL: drafted; see system.md.")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    for fn in (creative_strategist, opportunity_scout, creative_director_a,
               ecommerce_psychologist, graphic_designer, creative_director_b, copywriter,
               copy_editor, video_editor, analyst, media_buyer, offer_engineer):
        fn()
    n = len(list(OUT.rglob("*.md")))
    print(f"wrote {n} prompt files to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
