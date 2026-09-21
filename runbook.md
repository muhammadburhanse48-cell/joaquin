# Runbook

1. Python 3.11+ virtualenv, `pip install -r requirements.txt`.
2. `cp config/.env.example .env` and fill the three required values. The bot refuses to start
   (at startup, not first use) if one is missing.
3. `pytest` before every deploy (no network needed).
4. Start locally: `python -m bot.telegram_bot`.

## systemd (VPS)

`/etc/systemd/system/creative-os.service`

```ini
[Unit]
Description=Exposcale Creative OS Telegram bot
After=network-online.target

[Service]
WorkingDirectory=/opt/creative-os
ExecStart=/opt/creative-os/.venv/bin/python -m bot.telegram_bot
Restart=on-failure
RestartSec=5
User=creative

[Install]
WantedBy=multi-user.target
```

`sudo systemctl daemon-reload && sudo systemctl enable --now creative-os`; restart with
`sudo systemctl restart creative-os`; logs with `journalctl -u creative-os -f`.

Keep `.env`, `brands/` and `shared/` out of version control (already in `.gitignore`); back
them up, they are the client's data and the four flywheel files live there.

## Rotating the API key

Edit `.env`, `sudo systemctl restart creative-os`, run `python api_key_check.py`.

## Rebuilding prompts

Edit `prompts_source/<seat>.md`, run `python scripts/build_prompts.py`, run `pytest`.
