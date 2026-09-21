"""Environment-backed settings with startup validation."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    telegram_bot_token: str
    allowed_telegram_username: str
    model: str = "claude-sonnet-4-6"
    target_cpa: float = 30.0


def load_settings(*, require_required: bool = True) -> Settings:
    """Load env vars. Missing required keys fail here, at startup, not at first use."""
    load_dotenv()
    required = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "ALLOWED_TELEGRAM_USERNAME": os.getenv("ALLOWED_TELEGRAM_USERNAME", ""),
    }
    if require_required:
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
    return Settings(
        anthropic_api_key=required["ANTHROPIC_API_KEY"],
        telegram_bot_token=required["TELEGRAM_BOT_TOKEN"],
        allowed_telegram_username=required["ALLOWED_TELEGRAM_USERNAME"],
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        target_cpa=float(os.getenv("TARGET_CPA", "30")),
    )