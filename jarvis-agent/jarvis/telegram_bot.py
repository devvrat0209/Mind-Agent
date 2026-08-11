"""Telegram bot interface for JARVIS.

Run: jarvis-telegram
Or:  python -m jarvis.telegram_bot

Requires: TELEGRAM_BOT_TOKEN env var
"""

import os
import sys
import json
import asyncio
import logging
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


logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("jarvis.telegram")


class TelegramJarvis:
    """JARVIS on Telegram — full device access via chat."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.agent = Agent(self.config)
        # Per-chat agents to keep context separate
        self.chat_agents: dict[int, Agent] = {}
        # Authorized users (empty = anyone can use)
        self.authorized_users = self._load_authorized_users()

    def _load_authorized_users(self) -> set[int]:
        raw = os.getenv("JARVIS_TELEGRAM_USERS", "")
        if not raw:
            return set()
        return {int(uid.strip()) for uid in raw.split(",") if uid.strip().isdigit()}

    def _get_agent(self, chat_id: int) -> Agent:
        if chat_id not in self.chat_agents:
            self.chat_agents[chat_id] = Agent(self.config)
        return self.chat_agents[chat_id]

    def _is_authorized(self, user_id: int) -> bool:
        if not self.authorized_users:
            return True  # no restriction
        return user_id in self.authorized_users

    def setup_handlers(self, app):
        """Register all Telegram handlers."""
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("reset", self.cmd_reset))
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("inspect", self.cmd_inspect))
        app.add_handler(CommandHandler("diff", self.cmd_diff))
        app.add_handler(CommandHandler("rollback", self.cmd_rollback))
        app.add_handler(CommandHandler("model", self.cmd_model))
        app.add_handler(CommandHandler("shell", self.cmd_shell))
        # Photo handler (send image → JARVIS analyzes)
        app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        # Document handler
        app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        # Voice handler
        app.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        # Text handler (main chat)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

    # ── Commands ───────────────────────────────────────────

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔ Unauthorized. Set JARVIS_TELEGRAM_USERS with your Telegram user ID.")
            return
        await update.message.reply_text(
            "🤖 *J.A.R.V.I.S. Online*\n\n"
            "Just A Rather Very Intelligent System\n"
            "Full device access enabled.\n\n"
            "Talk to me naturally, or use /help for commands.",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 *JARVIS Commands*\n\n"
            "/start — Initialize\n"
            "/help — This message\n"
            "/reset — Reset conversation\n"
            "/status — Device status\n"
            "/inspect — Self-inspect source code\n"
            "/diff — Show git diff\n"
            "/rollback — Undo last edit\n"
            "/model — Change LLM model\n"
            "/shell — Run shell command\n\n"
            "_You can also just talk to me. I can read files, edit code (including myself), "
            "run commands, take screenshots, manage processes, and more._",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        agent = self._get_agent(update.effective_chat.id)
        agent.reset()
        await update.message.reply_text("🔄 Conversation reset.")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Quick system status using device tools
        agent = self._get_agent(update.effective_chat.id)
        result = agent.tools.device_tools.call("system_info", {})
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=1)
        await update.message.reply_text(
            f"🖥 *System Status*\n\n"
            f"CPU: {cpu}%\n"
            f"RAM: {mem.percent}% ({mem.used/1e9:.1f}/{mem.total/1e9:.1f} GB)\n"
            f"Procs: {len(psutil.pids())}\n"
            f"Workspace: `{self.config.workspace}`\n"
            f"Model: `{self.config.llm_model}`\n"
            f"Edits: {len(agent.tools.edit_stack)}",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_inspect(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        agent = self._get_agent(update.effective_chat.id)
        result = agent.tools.self_inspect()
        await update.message.reply_text(f"🔍 {result.output[:4000]}")

    async def cmd_diff(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        agent = self._get_agent(update.effective_chat.id)
        result = agent.tools.git_diff()
        text = result.output[:4000] or "(no changes)"
        await update.message.reply_text(f"```diff\n{text}\n```", parse_mode=ParseMode.MARKDOWN)

    async def cmd_rollback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        agent = self._get_agent(update.effective_chat.id)
        result = agent.tools.rollback()
        emoji = "✅" if not result.error else "❌"
        await update.message.reply_text(f"{emoji} {result.output}")

    async def cmd_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args or []
        if args:
            self.config.llm_model = args[0]
            await update.message.reply_text(f"✅ Model set to: `{args[0]}`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(f"Current model: `{self.config.llm_model}`\nUsage: /model openai/gpt-4o", parse_mode=ParseMode.MARKDOWN)

    async def cmd_shell(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args or []
        if not args:
            await update.message.reply_text("Usage: /shell <command>")
            return
        cmd = " ".join(args)
        agent = self._get_agent(update.effective_chat.id)
        result = agent.tools.shell(cmd)
        text = result.output[:4000] or "(no output)"
        await update.message.reply_text(f"```\n{text}\n```", parse_mode=ParseMode.MARKDOWN)

    # ── Message Handlers ───────────────────────────────────

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔ Unauthorized.")
            return

        user_text = update.message.text
        chat_id = update.effective_chat.id
        agent = self._get_agent(chat_id)

        # Show "thinking" indicator
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        try:
            response = agent.chat(user_text)
        except Exception as e:
            await update.message.reply_text(f"⚠ Error: {e}")
            return

        if not response:
            await update.message.reply_text("(no response)")
            return

        # Telegram message limit is 4096 chars
        for chunk in self._chunk_message(response, 4000):
            try:
                await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                # If markdown fails, send as plain text
                await update.message.reply_text(chunk)

        # Check if any files were created that should be sent
        await self._send_created_files(agent, update, context)

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update.effective_user.id):
            return
        # Download photo and tell agent about it
        photo = update.message.photo[-1]  # highest resolution
        file = await context.bot.get_file(photo.file_id)
        path = f"/tmp/jarvis_telegram_photo_{photo.file_id}.jpg"
        await file.download_to_drive(path)

        agent = self._get_agent(update.effective_chat.id)
        caption = update.message.caption or "What do you see in this image?"
        response = agent.chat(f"[User sent an image: {path}] {caption}")
        await update.message.reply_text(response[:4000])

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update.effective_user.id):
            return
        doc = update.message.document
        file = await context.bot.get_file(doc.file_id)
        path = str(self.config.workspace / doc.file_name)
        await file.download_to_drive(path)

        agent = self._get_agent(update.effective_chat.id)
        response = agent.chat(f"[User sent file: {path} ({doc.file_name})] I've saved it. What should I do with it?")
        await update.message.reply_text(response[:4000])

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update.effective_user.id):
            return
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        path = f"/tmp/jarvis_voice_{voice.file_id}.ogg"
        await file.download_to_drive(path)

        agent = self._get_agent(update.effective_chat.id)
        response = agent.chat(f"[User sent voice message: {path}] Transcribe or process this audio file.")
        await update.message.reply_text(response[:4000])

    # ── Helpers ────────────────────────────────────────────

    async def _send_created_files(self, agent: Agent, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """If agent created files, offer to send them."""
        if not agent.tools.edit_stack:
            return
        last = agent.tools.edit_stack[-1]
        path = last.get("path", "")
        if path and Path(path).exists() and Path(path).stat().st_size < 50_000_000:  # < 50MB
            try:
                if path.endswith((".png", ".jpg", ".jpeg", ".gif")):
                    await update.message.reply_photo(photo=open(path, "rb"))
                elif path.endswith((".py", ".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".csv")):
                    await update.message.reply_document(document=open(path, "rb"))
            except Exception:
                pass

    @staticmethod
    def _chunk_message(text: str, max_len: int = 4000) -> list[str]:
        """Split message into chunks that fit Telegram's limit."""
        if len(text) <= max_len:
            return [text]
        chunks = []
        while text:
            if len(text) <= max_len:
                chunks.append(text)
                break
            # Split at newline
            split_at = text.rfind("\n", 0, max_len)
            if split_at == -1:
                split_at = max_len
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        return chunks


def main():
    """Entry point for jarvis-telegram command."""
    token = os.getenv("JARVIS_TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ Set JARVIS_TELEGRAM_TOKEN or TELEGRAM_BOT_TOKEN env var")
        print("   Get a token from @BotFather on Telegram")
        sys.exit(1)

    config = Config()
    jarvis = TelegramJarvis(config)

    print("🤖 JARVIS Telegram Bot starting...")
    print(f"   Model: {config.llm_model}")
    print(f"   Workspace: {config.workspace}")
    print(f"   Source: {config.source_dir}")

    app = ApplicationBuilder().token(token).build()
    jarvis.setup_handlers(app)

    # Set bot commands
    async def post_init(application):
        await application.bot.set_my_commands([
            BotCommand("start", "Initialize JARVIS"),
            BotCommand("help", "Show commands"),
            BotCommand("status", "Device status"),
            BotCommand("reset", "Reset conversation"),
            BotCommand("inspect", "Self-inspect code"),
            BotCommand("diff", "Show changes"),
            BotCommand("rollback", "Undo last edit"),
            BotCommand("model", "Change LLM model"),
            BotCommand("shell", "Run shell command"),
        ])

    app.post_init = post_init

    print("✅ JARVIS is online. Talk to him on Telegram.")
    app.run_polling()


if __name__ == "__main__":
    main()
