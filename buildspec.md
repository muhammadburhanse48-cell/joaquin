# Build Spec: Exposcale Creative Operating System — Agent Pipeline

## What you're building

A Python system that automates a 12-seat AI creative production pipeline for
direct-response ecommerce ad creative (Meta). The full method is documented in
7 handbook PDFs ("Doc 00" through "Doc 06") that will be provided separately —
read them before writing code if they're available in the repo/context; if not,
follow this spec, which distills their structure.

Trigger: a single Telegram bot command runs the entire pipeline end-to-end,
automatically, from research through to a launch-ready batch and (on a later
command) a readout.

Runtime: Python 3.11+, async, deployed on a VPS as a systemd service.

---

## 1. Repo structure

Create exactly this layout:

```
project-root/
├── agents/
│   ├── __init__.py
│   ├── base_seat.py            # shared class — see Section 3
│   ├── seats/
│   │   ├── __init__.py
│   │   ├── creative_strategist.py
│   │   ├── opportunity_scout.py
│   │   ├── creative_director_a.py
│   │   ├── ecommerce_psychologist.py
│   │   ├── graphic_designer.py
│   │   ├── creative_director_b.py
│   │   ├── copywriter.py
│   │   ├── copy_editor.py
│   │   ├── video_editor.py
│   │   ├── analyst.py
│   │   ├── media_buyer.py
│   │   └── offer_engineer.py
│   └── prompts/
│       ├── creative_strategist/
│       │   ├── system.md
│       │   ├── task_mining_pass.md
│       │   ├── task_persona_cards.md
│       │   └── task_angle_bank.md
│       ├── opportunity_scout/
│       │   └── system.md
│       ├── creative_director_a/
│       │   ├── system.md
│       │   └── task_concept_portfolio.md
│       ├── ecommerce_psychologist/
│       │   ├── system.md
│       │   └── task_psych_review.md
│       ├── graphic_designer/
│       │   ├── system.md
│       │   └── task_generation_template.md
│       ├── creative_director_b/
│       │   ├── system.md
│       │   ├── task_judge_qa.md
│       │   └── task_batch_sweep.md
│       ├── copywriter/
│       │   ├── system.md
│       │   ├── task_ad.md
│       │   ├── task_advertorial.md
│       │   ├── task_pdp.md
│       │   └── task_email.md
│       ├── copy_editor/
│       │   ├── system.md
│       │   └── task_edit.md
│       ├── video_editor/
│       │   ├── system.md
│       │   ├── task_scripts.md
│       │   └── task_motion.md
│       ├── analyst/
│       │   ├── system.md
│       │   └── task_readout.md
│       ├── media_buyer/
│       │   ├── system.md
│       │   └── task_scaling_proposal.md
│       └── offer_engineer/
│           └── system.md
│
├── orchestrator/
│   ├── __init__.py
│   ├── loop.py                  # the 10 pipeline stages — see Section 4
│   ├── gates.py                 # blocking checks — see Section 5
│   └── brand_state.py           # reads/writes the per-brand folder tree
│
├── bot/
│   ├── __init__.py
│   ├── telegram_bot.py
│   └── auth.py                  # single-user allowlist by Telegram username
│
├── brands/
│   └── <BRAND_NAME>/            # created per client brand — see Section 2
│
├── shared/                      # cross-brand knowledge base — see Section 2
│
├── config/
│   ├── settings.py               # loads env vars, validates required keys present
│   └── .env.example
│
├── tests/
│   └── ...
│
├── requirements.txt
├── runbook.md                    # deploy/restart/env var instructions
├── .gitignore                    # MUST exclude .env, brands/*, shared/*
└── README.md
```

---

## 2. Per-brand and shared folder structure

Every brand gets this tree under `brands/<BRAND_NAME>/`. Create it
programmatically (a function in `brand_state.py`) rather than by hand, since
a new client brand should be one function call.

```
brands/<BRAND_NAME>/
├── 01_account-audit/
│   └── account-report-<date>.md
├── 02_landing-page/
│   └── advertorials/
├── 03_research/
│   ├── customer-language.md
│   ├── persona-cards.md
│   ├── market-diagnosis.md
│   └── winning-concepts.md
├── 04_angles-scripts/
│   └── angle-bank.md
├── 05_creatives/
│   ├── B01/                      # per batch: candidates, briefs, qa-log, copy sheet
│   └── B01_for_drive/            # flat, numbered, shipping files
├── 06_briefs-out/
│   ├── launch-plan-B01.md
│   └── video/B01/
├── 07_results/
│   ├── results-log.md            # one row per ad per readout — THE flywheel file
│   └── angle-performance.md
└── _product-assets/              # real product photographs
```

Shared across all brands (`shared/`):

```
shared/
├── creative-ledger.md            # every batch + concept ever shipped, never repeat
├── winning-variables.md          # proven hooks/angles/formats, with T1 evidence
├── creative-learnings.md         # cross-brand principles, numbers attached
├── visual-pattern-library/       # per niche: <niche>.md
├── swipe-vault/<niche>/          # 8-15 curated reference images + manifest.json
├── opportunity-backlog.md
└── format-radar.md
```

**Note the four files that matter most** (call this out in code comments):
`results-log.md`, `creative-ledger.md`, `customer-language.md`,
`winning-variables.md`. If any orchestration corner gets cut under time
pressure, these four must not be it.

---

## 3. `base_seat.py` — the shared agent class

This is the most important file in the repo. Every seat is an instance of
this class with a different system prompt and refusal set. **The critical
requirement: a seat call is stateless.** No conversation history is ever
carried between calls. Each call receives only its own explicitly declared
evidence base as a dict, passed into the prompt template — never a shared
chat thread, and never another seat's reasoning or draft.

This enforces the system's core law: **the critic must never see the
author's brief or reasoning.** If you build this as a single long-running
conversation instead of isolated stateless calls, the whole system's
judging becomes worthless — a model that can read its own justification for
why something should work will simply agree with itself.

```python
import anthropic
from pathlib import Path
from dataclasses import dataclass, field

@dataclass
class SeatResult:
    seat_name: str
    output_text: str
    raw_response: object

class BaseSeat:
    """
    One seat = one system prompt + a strict evidence-base contract.
    Every .run() call is a fresh, isolated API call. No history is retained
    or passed between calls, ever.
    """

    def __init__(self, seat_name: str, prompts_dir: Path,
                 model: str = "claude-sonnet-4-6"):
        self.seat_name = seat_name
        self.system_prompt = (prompts_dir / "system.md").read_text()
        self.model = model
        self.client = anthropic.Anthropic()  # ANTHROPIC_API_KEY from env

    def run(self, task_prompt_template: str, evidence: dict,
            attached_images: list[bytes] | None = None,
            max_tokens: int = 8000) -> SeatResult:
        """
        task_prompt_template: the task-specific .md prompt, with
            <placeholder> tokens matching evidence dict keys.
        evidence: explicit dict of ONLY what this seat is allowed to see.
            Never pass another seat's brief/rationale to a critic seat.
        """
        filled_prompt = self._fill_template(task_prompt_template, evidence)
        content = [{"type": "text", "text": filled_prompt}]
        for img_bytes in (attached_images or []):
            content.insert(0, {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png",
                           "data": self._b64(img_bytes)}
            })
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=self.system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        return SeatResult(self.seat_name, text, response)

    def _fill_template(self, template: str, evidence: dict) -> str:
        out = template
        for key, value in evidence.items():
            out = out.replace(f"<{key}>", str(value))
        return out

    @staticmethod
    def _b64(data: bytes) -> str:
        import base64
        return base64.b64encode(data).decode()
```

Each file under `agents/seats/` is a thin subclass or factory that loads the
right prompt directory and exposes named methods matching that seat's task
prompts (e.g. `creative_director_b.py` exposes `.judge_and_qa(...)` and
`.batch_sweep(...)`, both calling `self.run(...)` with different templates
and — critically — NOT receiving the brief/hypothesis that produced the
images they're judging).

---

## 4. The 12 seats — what each one does and refuses

| Seat | Role | Reads | Writes | REFUSES |
|---|---|---|---|---|
| Creative Strategist | Mines voice-of-customer, builds persona cards, angle bank | reviews, comments, forum threads, competitor copy | `customer-language.md`, `persona-cards.md`, `market-diagnosis.md` | asserting anything without a verbatim quote + source |
| Opportunity Scout | Hunts new angles, rising formats | format radar, backlog | additions to `opportunity-backlog.md`, `format-radar.md` | logging an opportunity with no signal behind it |
| Creative Director (Mode A) | Turns evidence into concept briefs | account report, persona cards, angle bank, pattern library, ledger | 10 concept briefs per batch | writing the generation prompt for an image it will later judge |
| Ecommerce Psychologist | Pre-spend gut-check: will this persona act? | the 10 concepts (NOT the director's reasoning), persona cards | PASS/FIX/SWAP verdict table | authoring concepts, researching new data, looping more than once |
| Graphic Designer | Writes generation prompts, generates candidates | briefs, product photo reference | 2-3 image candidates per slot | scoring or shipping its own candidates |
| Creative Director (Mode B) | Judge panel + QA critique — **isolated seat** | ONLY: images, product photo, persona card, brand rules, competitor exemplar, landing page promise | SHIP/REGEN verdicts, 7-lever scores | reviewing work while holding the brief that produced it — refuse and flag if a brief is accidentally included |
| Copywriter | Ad copy, advertorials, PDP, email | persona cards, customer language, concept table, offer | copy sheet + drafts | inventing a quote, review, or statistic |
| Copy Editor | Mechanical fixes + bounces substantive issues | the draft, persona cards, customer language, feeding creative | edited copy, bounce log, 7-lever score | authoring angles or claims itself |
| Video Editor | Scripts, motion prompts, assemblies | persona cards, angle bank, video pattern library, results log | scene-table scripts, motion prompts | judging its own output, animating a killed/unshipped creative |
| Analyst | The readout — pulls numbers, applies verdicts | ad-level data (3d/7d/lifetime), country breakdown, economics, ledger | `results-log.md` rows, promoted `winning-variables.md` entries | writing a verdict without numbers, judging below the spend floor |
| Media Buyer | Turns readout into scaling proposals | analyst's verdict rows, current campaign structure | budget/cap-move proposals | touching the live ad account — proposals only, never executes |
| Offer Engineer | Called when data says offer is the constraint | economics, CPA/ROAS data | price/bundle/guarantee rebuild proposal | changing live prices without approval |

---

## 5. Orchestrator — the 10-stage loop and its gates

`orchestrator/loop.py` implements one full cycle as ten stages, run in order.
`orchestrator/gates.py` implements **blocking** checks — a gate that fails
must halt the stage and report why, not just log a warning and continue.

```python
STAGES = [
    "preflight",            # Stage 0 — gates.py checks; print RUN/REUSE/SKIP plan
    "research",             # Stage 1 — Creative Strategist (only if gate says RUN)
    "pattern_mining",       # Stage 2 — Opportunity Scout / pattern library refresh
    "concept_portfolio",    # Stage 3 — Creative Director A, 10 concepts
    "psych_review",         # Stage 4 — Ecommerce Psychologist, ISOLATED from stage 3's reasoning
    "production",           # Stage 5 — Graphic Designer, generates candidates
    "judge_and_qa",         # Stage 6 — Creative Director B, ISOLATED, no brief attached
    "copy",                 # Stage 7 — Copywriter then Copy Editor
    "launch_plan",          # Stage 8 — assembles launch plan, PROPOSAL ONLY
    "readout",              # Stage 9 — Analyst, only after spend floor met (separate trigger)
]
```

### Blocking gates (implement as functions returning `(passed: bool, reason: str)`)

- **Flywheel gate**: block a new batch if the previous batch has spend logged
  but no written readout in `results-log.md`. Exception: brand has never
  launched a batch.
- **Research freshness**: research files in `03_research/` must be under 14
  days old, or explicitly invalidated by the last readout.
- **Pattern gate**: `visual-pattern-library/<niche>.md` and the matching
  swipe vault must both exist and be under 30 days old.
- **Spend floor**: no verdict is produced for a creative below its spend
  floor (default ≥1.5× target CPA, or $30/creative fallback). This gate
  lives inside the Analyst seat's stage, not the orchestrator, but the
  orchestrator must never call the Analyst with data that skips this check.
- **QA gate**: Creative Director B's score must be ≥11/14 with zero
  hard-gate failures (product inaccuracy, landing-page-incongruent promise,
  illegible text, safe-margin breach) or the creative does not proceed to
  copy/launch — it goes back to Graphic Designer for regeneration (max 3
  rounds, then escalate to the human).

### Context isolation enforcement (put this check directly in `loop.py`)

Before calling Creative Director B (Stage 6) or the Ecommerce Psychologist
(Stage 4), assert that the evidence dict passed does NOT contain any key
matching `brief`, `hypothesis`, `rationale`, or `director_notes`. Raise an
error rather than silently proceeding if one is present. This is a
deliberate guard against a future code change accidentally leaking author
context into a critic call.

---

## 6. Telegram bot

`bot/telegram_bot.py` using `python-telegram-bot`.

- **Auth**: `bot/auth.py` checks `update.effective_user.username` against a
  single allowed username from env (`ALLOWED_TELEGRAM_USERNAME`). Reject
  silently (no reply) for anyone else.
- **Commands**:
  - `/run <brand>` — kicks off the full 10-stage loop (Stages 0-8) for the
    named brand as a background `asyncio` task. Does NOT block the handler.
    Sends progress messages to the chat as each stage completes
    ("Stage 3/10: Concept portfolio — 10 concepts drafted").
  - `/readout <brand>` — runs Stage 9 only, once spend data is available.
  - `/status <brand>` — reports where an in-progress run currently is.
- Run the bot as a `systemd` service on the VPS so it restarts automatically
  on crash or reboot.

---

## 7. Environment variables required

```
ANTHROPIC_API_KEY=
TELEGRAM_BOT_TOKEN=
ALLOWED_TELEGRAM_USERNAME=
# Add as they become available:
# OPENAI_API_KEY=
# HIGGSFIELD_API_KEY=
# META_ACCESS_TOKEN=
# SHOPIFY_ADMIN_TOKEN=
# KLAVIYO_API_KEY=
```

`config/settings.py` should load these via `python-dotenv`, and fail loudly
at startup (not at first use) if a required key for an enabled seat is
missing.

---

## 8. Build order (do not skip ahead)

1. Scaffold the full folder tree from Sections 1-2, empty files where noted.
2. Implement `base_seat.py` exactly as in Section 3, with the isolation
   guard from Section 5.
3. Populate `agents/prompts/creative_strategist/`,
   `agents/prompts/creative_director_a/`, and
   `agents/prompts/ecommerce_psychologist/` with the seat + task prompts
   (verbatim text will be supplied from the source handbook docs — do not
   paraphrase or invent these prompts).
4. Implement those three seats' Python wrapper classes.
5. Write a local test script that runs: Strategist → Creative Director A →
   Ecommerce Psychologist on a small hand-written evidence set, and
   manually confirm the Psychologist's call received none of Creative
   Director A's brief/reasoning — inspect the actual API request payload,
   don't just trust the code.
6. Implement `orchestrator/gates.py` and get the preflight stage (Stage 0)
   working standalone, printing the RUN/REUSE/SKIP plan.
7. Wire Stages 1, 3, 4 into `orchestrator/loop.py` using the three seats
   built above, gated by Stage 0's preflight.
8. Build `bot/telegram_bot.py` with `/run` triggering that partial loop as
   a background task with progress messages.
9. Only after 5-8 work end-to-end: add the remaining 9 seats
   (Opportunity Scout, Graphic Designer, Creative Director B, Copywriter,
   Copy Editor, Video Editor, Analyst, Media Buyer, Offer Engineer) and
   extend the loop to all 10 stages.
10. Deploy to the VPS as a `systemd` service once a full local dry run
    completes without errors.

Do not attempt to build all 12 seats before step 5 validates the isolation
pattern — that pattern is the part most likely to have a subtle bug, and
it's cheapest to catch with 3 seats wired up, not 12.