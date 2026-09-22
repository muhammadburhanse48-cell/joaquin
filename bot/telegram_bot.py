"""Telegram commands. Everyone except the one allowed username is ignored silently."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from config.settings import load_settings
from orchestrator.brand_state import mark_launched
from orchestrator.errors import AlreadyRunning
from orchestrator.loop import LABELS, STAGES, Pipeline

from .auth import is_allowed

log = logging.getLogger(__name__)
TELEGRAM_LIMIT = 3900


class TelegramService:
    def __init__(self, root: Path, allowed_username: str, model: str = "claude-sonnet-4-6",
                 max_parallel: int = 4, max_parallel_images: int = 2):
        self.root = Path(root)
        self.pipeline = Pipeline(self.root, model=model, max_parallel=max_parallel,
                                 max_parallel_images=max_parallel_images)
        self.allowed_username = allowed_username
        self.tasks: dict[str, asyncio.Task] = {}

    def _brand_arg(self, context) -> str | None:
        return context.args[0] if context.args else None

    @staticmethod
    def _sender(update):
        async def send(message: str) -> None:
            await update.message.reply_text(message[:TELEGRAM_LIMIT])
        return send

    def _spawn(self, brand: str, coro) -> None:
        """Run as a background task so the handler returns immediately."""
        task = asyncio.create_task(coro)
        self.tasks[brand] = task

        def done(t: asyncio.Task) -> None:
            self.tasks.pop(brand, None)
            if not t.cancelled() and t.exception():
                log.error("pipeline task for %s failed: %r", brand, t.exception())

        task.add_done_callback(done)

    async def run_command(self, update, context) -> None:
        if not is_allowed(update, self.allowed_username):
            return
        brand = self._brand_arg(context)
        if not brand:
            await update.message.reply_text("Usage: /run <brand>")
            return
        if self.pipeline.is_running(brand):
            await update.message.reply_text(f"{brand} already has a run in progress — see /status {brand}")
            return
        await update.message.reply_text(f"Starting {brand}: Stage 0/10 preflight")
        self._spawn(brand, self._guard(self.pipeline.run(brand, self._sender(update)), update))

    async def readout_command(self, update, context) -> None:
        if not is_allowed(update, self.allowed_username):
            return
        brand = self._brand_arg(context)
        if not brand:
            await update.message.reply_text("Usage: /readout <brand>")
            return
        if self.pipeline.is_running(brand):
            await update.message.reply_text(f"{brand} already has a run in progress — see /status {brand}")
            return
        await update.message.reply_text(f"Readout started for {brand} (Stage 9/10)")
        self._spawn(brand, self._guard(self.pipeline.readout(brand, self._sender(update)), update))

    async def status_command(self, update, context) -> None:
        if not is_allowed(update, self.allowed_username):
            return
        brand = self._brand_arg(context)
        if not brand:
            await update.message.reply_text("Usage: /status <brand>")
            return
        s = self.pipeline.get_status(brand)
        stage = s.current_stage
        where = f"Stage {STAGES.index(stage)}/10: {LABELS[stage]}" if stage in STAGES else stage
        text = f"{brand} {s.batch or ''}: {s.state} — {where}; {len(s.completed)} stage(s) done"
        await update.message.reply_text((text + ("\n" + s.message if s.message else ""))[:TELEGRAM_LIMIT])

    async def launched_command(self, update, context) -> None:
        """/launched <brand> <batch> [spend] — record that a staged batch went live (arms the flywheel gate)."""
        if not is_allowed(update, self.allowed_username):
            return
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /launched <brand> <batch, e.g. B01> [spend]")
            return
        brand, batch = context.args[0], context.args[1].upper()
        try:
            spend = float(context.args[2]) if len(context.args) > 2 else None
            mark_launched(self.root / "brands" / brand, batch, spend)
        except (ValueError, FileNotFoundError) as exc:
            await update.message.reply_text(f"Could not mark launched: {exc}")
            return
        await update.message.reply_text(f"{brand} {batch} marked launched. No new batch until /readout {brand} is written.")

    @staticmethod
    async def _guard(coro, update) -> None:
        try:
            await coro
        except AlreadyRunning as exc:
            await update.message.reply_text(str(exc))
        except Exception as exc:  # the run already recorded FAILED; tell the human too
            await update.message.reply_text(f"Run failed: {exc}"[:TELEGRAM_LIMIT])


def build_application(service: TelegramService):
    try:
        from telegram.ext import Application, CommandHandler
    except ImportError as exc:
        raise RuntimeError("python-telegram-bot is required to run the bot") from exc
    application = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    for name, handler in (("run", service.run_command), ("readout", service.readout_command),
                          ("status", service.status_command), ("launched", service.launched_command)):
        application.add_handler(CommandHandler(name, handler))
    return application


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()  # fails loudly at startup if a required key is missing
    service = TelegramService(Path.cwd(), settings.allowed_telegram_username, settings.model,
                              settings.max_parallel, settings.max_parallel_images)
    build_application(service).run_polling()


if __name__ == "__main__":
    main()
