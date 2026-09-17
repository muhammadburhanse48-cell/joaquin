# Runbook

1. Create a Python 3.11 virtual environment and install `requirements.txt`.
2. Copy `config/.env.example` to `.env` and fill the required values.
3. Run `pytest` before deployment.
4. Start locally with `python -m bot.telegram_bot`.

For systemd, set `WorkingDirectory` to this repo, `ExecStart` to the virtualenv
Python executable followed by `-m bot.telegram_bot`, and `Restart=on-failure`.
Keep `.env`, `brands/`, and `shared/` outside version control.