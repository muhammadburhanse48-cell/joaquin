# Exposcale Creative Operating System

An async Python pipeline that runs the 12-seat creative loop from the client handbook
(`docs/00`–`06`) for a direct-response ecommerce brand on Meta. One Telegram command runs
Stages 0–8 (preflight → launch plan); `/readout` runs Stage 9. Every seat call is a fresh,
stateless Anthropic request built only from an explicit evidence dict, so critics never see
the author's brief or reasoning (Law 2).

## How it maps to the handbook

| Handbook | Where it is enforced |
|---|---|
| Law 1 — data first, no invented quotes | quote audit on the mining pass (`03_research/quote-audit.md`), `winning-variables` rows need T1 numbers |
| Law 2 — critic ≠ author | `BaseSeat.critic` asserts isolation inside `run()`; Psychologist gets the concept *table* only; CD-B / Copy Editor / script gate refuse briefs |
| Law 3 — no readout, no next batch | `gates.flywheel_gate` stops the run; `/launched` arms it, `/readout` clears it |
| 14-day research / 30-day pattern gates | `gates.py` (RUN vs REUSE at preflight, re-checked after the refresh stage) |
| No brief, no production | `gates.brief_gate` |
| QA ≥ 11/14 + hard gates, max 3 rounds | `gates.qa_gate` decides SHIP in code, not from the model's prose; then escalates to the human |
| Batch sweep (10 checks) | `stages._sweep`; any FAIL stops staging |
| Copy: writer → editor, one bounce | `stages.stage_copy`, `gates.copy_gate` / `copy_lint` |
| Spend floor (1.5× target CPA, $30 fallback) | `gates.spend_floor_gate` before the Analyst is called; `enforce_spend_floor` after |
| Compliance flags, never blocks | compliance list is written to `B<NN>_for_drive/`, nothing gates on it |
| Media Buyer proposes, never executes | no code path touches an ad account; the launch plan is a file |

## Quick start

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp config/.env.example .env      # fill ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, ALLOWED_TELEGRAM_USERNAME
pytest
python -m orchestrator.loop --brand Acme --init     # creates brands/Acme/ and a brand.json stub
# fill brands/Acme/brand.json, then:
python -m orchestrator.loop --brand Acme --dry-run  # Stage 0 RUN/REUSE/STOP plan
python -m bot.telegram_bot                          # /run Acme
```

## What you supply (the pipeline reads files, it never guesses)

- `brands/<brand>/brand.json` — niche, product, offer + qualifier, landing-page promise, palette, …
- `03_research/source/*.md` — raw reviews, comments, forum threads, competitor copy (≥2 files)
- `_product-assets/` — the real product photograph
- `shared/swipe-vault/<niche>/incoming/` — 15–40 competitor winner images + `evidence.md`
- `01_account-audit/account-report-<date>.md`, `02_landing-page/` — when the brand has live ads
- candidate images per slot (see *Images* below) until an image generator is plugged in
- `07_results/exports/{ads-3d,ads-7d,ads-lifetime,country}.csv` for `/readout`

When something is missing the run stops with `NEEDS INPUT: …` naming the exact path; run
the same command again and it resumes where it stopped (state: `05_creatives/B<NN>/batch.json`).

## Commands

`/run <brand>` · `/readout <brand>` · `/status <brand>` · `/launched <brand> <B01> [spend]`

## Images

The client's stack uses `nano_banana_pro` (Gemini) / `gpt_image_2`; no key for either is configured.
By default the pipeline writes each generation prompt to `05_creatives/B<NN>/prompts/`, then
waits for 2–3 candidates in `candidates/<NN>/r<round>/`. To automate it, implement
`orchestrator.imagegen.ImageSource.generate()` (it must attach the product photo) and pass it to
`Pipeline(image_source=...)`.

## Prompts

`prompts_source/` holds the client's prompts verbatim. `python scripts/build_prompts.py`
rebuilds `agents/prompts/` from them (slots named, chat-only "confirm and wait" lines removed,
system/task split). Anything not from the client is marked `GAP-FILL` / `ORCHESTRATION`.
