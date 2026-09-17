# Exposcale Creative Operating System

An async Python pipeline for direct-response ecommerce creative production.
The pipeline uses isolated, stateless Anthropic calls for each seat. Critic
seats receive only their declared evidence and reject leaked author context.

## Quick start

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp config/.env.example .env
pytest
python -m orchestrator.loop --brand Demo --niche ecommerce
```

Populate `.env` before starting the Telegram bot. Brand folders are created by
`initialize_brand`; do not commit client data. The four protected flywheel files
are `results-log.md`, `creative-ledger.md`, `customer-language.md`, and
`winning-variables.md`.