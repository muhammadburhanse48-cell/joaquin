"""Telegram commands for background pipeline runs."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from .auth import is_allowed
from config.settings import load_settings
from orchestrator.loop import Pipeline, STAGES


class TelegramService:
    def __init__(self, root: Path, allowed_username: str):
        self.pipeline = Pipeline(root)
        self.allowed_username = allowed_username
        self.tasks: dict[str, asyncio.Task] = {}

    async def run_command(self, update, context) -> None:
        if not is_allowed(update, self.allowed_username):
            return
        if not context.args:
            await update.message.reply_text("Usage: /run <brand>")
            return
        brand = context.args[0]
        await update.message.reply_text(f"Starting {brand}: Stage 0/10 preflight")

        async def progress(message: str) -> None:
            await update.message.reply_text(message)

        task = asyncio.create_task(self.pipeline.run(brand, "general", progress=progress))
        self.tasks[brand] = task
        task.add_done_callback(lambda _: self.tasks.pop(brand, None))

    async def readout_command(self, update, context) -> None:
        if not is_allowed(update, self.allowed_username):
            return
        if context.args:
            await update.message.reply_text(f"Readout queued for {context.args[0]}")

    async def status_command(self, update, context) -> None:
        if not is_allowed(update, self.allowed_username):
            return
        if not context.args:
            return
        status = self.pipeline.get_status(context.args[0])
        await update.message.reply_text(
            f"{status.brand}: {status.current_stage}; completed {len(status.completed)}/{len(STAGES)}"
        )


def build_application(service: TelegramService):
    try:
        from telegram.ext import Application, CommandHandler
    except ImportError as exc:
        raise RuntimeError("python-telegram-bot is required to run the bot") from exc
    application = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    application.add_handler(CommandHandler("run", service.run_command))
    application.add_handler(CommandHandler("readout", service.readout_command))
    application.add_handler(CommandHandler("status", service.status_command))
    return application


def main() -> None:
    settings = load_settings()
    service = TelegramService(Path.cwd(), settings.allowed_telegram_username)
    build_application(service).run_polling()


if __name__ == "__main__":
    main()