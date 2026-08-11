"""Telegram bot interface for JARVIS — VPS-optimized.

Run: jarvis-telegram
Or:  python -m jarvis.telegram_bot

Requires: JARVIS_TELEGRAM_TOKEN env var
"""

import os
import sys
import json
import asyncio
import logging
import signal
import traceback
from pathlib import Path
from typing import Optional

from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

from .config import Config
from .agent import Agent

# Logging — file + stdout for VPS
log_dir = Path(os.getenv("JARVIS_LOG_DIR", "/var/log/jarvis"))
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / "jarvis.log"),
    ],
)
logger = logging.getLogger("jarvis.telegram")


class TelegramJarvis:
    """JARVIS on Telegram — full device access via chat. VPS-ready."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        # Single agent instance (VPS = single user)
        self.agent = Agent(self.config)
        self.authorized_users = self._load_authorized_users()
        self.owner_id: Optional[int] = None  # set on first /start

    def _load_authorized_users(self) -> set[int]:
        raw = os.getenv("JARVIS_TELEGRAM_USERS", "")
        if not raw:
            return set()
        return {int(uid.strip()) for uid in raw.split(",") if uid.strip().isdigit()}

    def _is_authorized(self, user_id: int) -> bool:
        if not self.authorized_users:
            return True
        return user_id in self.authorized_users

    def setup_handlers(self, app):
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("reset", self.cmd_reset))
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("inspect", self.cmd_inspect))
        app.add_handler(CommandHandler("diff", self.cmd_diff))
        app.add_handler(CommandHandler("rollback", self.cmd_rollback))
        app.add_handler(CommandHandler("model", self.cmd_model))
        app.add_handler(CommandHandler("shell", self.cmd_shell))
        app.add_handler(CommandHandler("restart", self.cmd_restart))
        app.add_handler(CommandHandler("log", self.cmd_log))
        app.add_handler(CommandHandler("uptime", self.cmd_uptime))
        # Media
        app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        app.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        # Text
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

    # ── Commands ───────────────────────────────────────────

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not self._is_authorized(uid):
            await update.message.reply_text(
                f"⛔ Unauthorized (your ID: `{uid}`).\n"
                f"Add your ID to JARVIS_TELEGRAM_USERS env var.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        self.owner_id = uid
        import psutil
        mem = psutil.virtual_memory()
        await update.message.reply_text(
            "🤖 *J.A.R.V.I.S. Online*\n\n"
            "Just A Rather Very Intelligent System\n"
            f"Server: `{self.config.workspace}`\n"
            f"RAM: {mem.total/1e9:.1f} GB | CPUs: {os.cpu_count()}\n"
            f"Model: `{self.config.llm_model}`\n\n"
            "Full device access. Talk to me naturally.",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 *JARVIS Commands*\n\n"
            "/start — Initialize\n"
            "/help — This message\n"
            "/reset — Reset conversation\n"
            "/status — Server status\n"
            "/uptime — Uptime info\n"
            "/inspect — Self-inspect source\n"
            "/diff — Git diff\n"
            "/rollback — Undo last edit\n"
            "/model — Change LLM\n"
            "/shell — Run shell command\n"
            "/log — View recent logs\n"
            "/restart — Restart service\n\n"
            "_Or just talk. I can read/write/edit code (including myself), "
            "run commands, manage processes, download files, and more._",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.agent.reset()
        await update.message.reply_text("🔄 Conversation reset.")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        import psutil
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=1)
        disk = psutil.disk_usage("/")
        uptime_s = int(time.time() - psutil.boot_time())
        d, r = divmod(uptime_s, 86400)
        h, r = divmod(r, 3600)
        m, s = divmod(r, 60)

        await update.message.reply_text(
            f"🖥 *Server Status*\n\n"
            f"CPU: `{cpu}%`\n"
            f"RAM: `{mem.percent}%` ({mem.used/1e9:.1f}/{mem.total/1e9:.1f} GB)\n"
            f"Disk: `{disk.percent}%` ({disk.used/1e9:.1f}/{disk.total/1e9:.1f} GB)\n"
            f"Procs: `{len(psutil.pids())}`\n"
            f"Uptime: `{d}d {h}h {m}m`\n"
            f"Model: `{self.config.llm_model}`\n"
            f"Edits: `{len(self.agent.tools.edit_stack)}`\n"
            f"Workspace: `{self.config.workspace}`",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_uptime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        import psutil
        uptime_s = int(time.time() - psutil.boot_time())
        d, r = divmod(uptime_s, 86400)
        h, r = divmod(r, 3600)
        m, s = divmod(r, 60)
        await update.message.reply_text(f"⏱ Uptime: {d}d {h}h {m}m {s}s")

    async def cmd_inspect(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        result = self.agent.tools.self_inspect()
        text = result.output[:4000]
        await update.message.reply_text(f"```\n{text}\n```", parse_mode=ParseMode.MARKDOWN)

    async def cmd_diff(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        result = self.agent.tools.git_diff()
        text = result.output[:4000] or "(no changes)"
        await update.message.reply_text(f"```diff\n{text}\n```", parse_mode=ParseMode.MARKDOWN)

    async def cmd_rollback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        result = self.agent.tools.rollback()
        emoji = "✅" if not result.error else "❌"
        await update.message.reply_text(f"{emoji} {result.output}")

    async def cmd_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args or []
        if args:
            self.config.llm_model = args[0]
            await update.message.reply_text(f"✅ Model: `{args[0]}`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(f"Model: `{self.config.llm_model}`\nUsage: `/model openai/gpt-4o`", parse_mode=ParseMode.MARKDOWN)

    async def cmd_shell(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args or []
        if not args:
            await update.message.reply_text("Usage: `/shell <command>`", parse_mode=ParseMode.MARKDOWN)
            return
        cmd = " ".join(args)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        result = self.agent.tools.shell(cmd)
        text = result.output[:4000] or "(no output)"
        await update.message.reply_text(f"```\n{text}\n```", parse_mode=ParseMode.MARKDOWN)

    async def cmd_restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Restart the JARVIS systemd service."""
        await update.message.reply_text("🔄 Restarting JARVIS service...")
        os.system("systemctl restart jarvis 2>/dev/null || echo 'not running as systemd service'")

    async def cmd_log(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show last 50 lines of log."""
        log_file = log_dir / "jarvis.log"
        if log_file.exists():
            lines = log_file.read_text().strip().split("\n")[-50:]
            text = "\n".join(lines)
            await update.message.reply_text(f"```\n{text[-4000:]}\n```", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("No log file found.")

    # ── Message Handlers ───────────────────────────────────

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔ Unauthorized.")
            return

        user_text = update.message.text
        chat_id = update.effective_chat.id

        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        try:
            response = self.agent.chat(user_text)
        except Exception as e:
            logger.error(f"Agent error: {e}\n{traceback.format_exc()}")
            await update.message.reply_text(f"⚠ Error: {e}")
            return

        if not response:
            await update.message.reply_text("(no response)")
            return

        for chunk in self._chunk_message(response, 4000):
            try:
                await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                await update.message.reply_text(chunk)

        await self._send_created_files(update, context)

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update.effective_user.id):
            return
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        path = f"/tmp/jarvis_photo_{photo.file_id}.jpg"
        await file.download_to_drive(path)

        caption = update.message.caption or "What do you see in this image?"
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        response = self.agent.chat(f"[User sent image: {path}] {caption}")
        for chunk in self._chunk_message(response, 4000):
            await update.message.reply_text(chunk)

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update.effective_user.id):
            return
        doc = update.message.document
        file = await context.bot.get_file(doc.file_id)
        path = str(self.config.workspace / doc.file_name)
        await file.download_to_drive(path)

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        response = self.agent.chat(f"[User sent file: {path} ({doc.file_name})] Saved. What should I do with it?")
        await update.message.reply_text(response[:4000])

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update.effective_user.id):
            return
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        path = f"/tmp/jarvis_voice_{voice.file_id}.ogg"
        await file.download_to_drive(path)

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        response = self.agent.chat(f"[Voice message: {path}] Transcribe or process this audio.")
        await update.message.reply_text(response[:4000])

    # ── Helpers ────────────────────────────────────────────

    async def _send_created_files(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.agent.tools.edit_stack:
            return
        last = self.agent.tools.edit_stack[-1]
        path = last.get("path", "")
        if path and Path(path).exists() and Path(path).stat().st_size < 50_000_000:
            try:
                if path.endswith((".png", ".jpg", ".jpeg", ".gif")):
                    await update.message.reply_photo(photo=open(path, "rb"))
                elif path.endswith((".py", ".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".csv")):
                    await update.message.reply_document(document=open(path, "rb"))
            except Exception:
                pass

    @staticmethod
    def _chunk_message(text: str, max_len: int = 4000) -> list[str]:
        if len(text) <= max_len:
            return [text]
        chunks = []
        while text:
            if len(text) <= max_len:
                chunks.append(text)
                break
            split_at = text.rfind("\n", 0, max_len)
            if split_at == -1:
                split_at = max_len
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        return chunks


import time  # needed for uptime


def main():
    """Entry point for jarvis-telegram."""
    # Load .env file if present
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env")
    except ImportError:
        pass

    token = os.getenv("JARVIS_TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ Set JARVIS_TELEGRAM_TOKEN in .env or environment")
        print("   Get a token from @BotFather on Telegram")
        sys.exit(1)

    config = Config()
    jarvis = TelegramJarvis(config)

    logger.info(f"JARVIS Telegram Bot starting")
    logger.info(f"  Model: {config.llm_model}")
    logger.info(f"  Workspace: {config.workspace}")
    logger.info(f"  Source: {config.source_dir}")
    logger.info(f"  Authorized users: {jarvis.authorized_users or '(anyone)'}")

    app = ApplicationBuilder().token(token).build()
    jarvis.setup_handlers(app)

    async def post_init(application):
        await application.bot.set_my_commands([
            BotCommand("start", "Initialize JARVIS"),
            BotCommand("help", "Show commands"),
            BotCommand("status", "Server status"),
            BotCommand("uptime", "Server uptime"),
            BotCommand("reset", "Reset conversation"),
            BotCommand("inspect", "Self-inspect code"),
            BotCommand("diff", "Show changes"),
            BotCommand("rollback", "Undo last edit"),
            BotCommand("model", "Change LLM model"),
            BotCommand("shell", "Run shell command"),
            BotCommand("log", "View recent logs"),
            BotCommand("restart", "Restart service"),
        ])
        logger.info("Bot commands registered")

    app.post_init = post_init

    logger.info("✅ JARVIS online — polling Telegram")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
