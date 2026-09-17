"""Single-user Telegram authorization."""

from __future__ import annotations


def is_allowed(update, allowed_username: str) -> bool:
    user = getattr(update, "effective_user", None)
    return bool(user and user.username and user.username == allowed_username.lstrip("@"))