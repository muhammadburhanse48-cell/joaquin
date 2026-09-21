"""Single-user Telegram authorization by username (case-insensitive, as Telegram treats them)."""

from __future__ import annotations


def is_allowed(update, allowed_username: str) -> bool:
    user = getattr(update, "effective_user", None)
    if not (user and user.username and allowed_username):
        return False
    return user.username.lower() == allowed_username.lstrip("@").lower()
