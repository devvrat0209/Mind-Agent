"""Telegram bot interface for JARVIS — VPS-optimized.

Run: jarvis-telegram
Or:  python -m jarvis.telegram_bot

Requires: JARVIS_TELEGRAM_TOKEN env var
"""

import os
import sys
import json
import time
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
from .heartbeat import get_heartbeat, heartbeat_enabled, format_status

# Logging — file + stdout for VPS.
# Fall back to a writable location when /var/log isn't ours (user installs,
# Termux, unprivileged containers).
def _resolve_log_dir() -> Path:
    candidates = [os.getenv("JARVIS_LOG_DIR"), "/var/log/jarvis",
                  str(Path.home() / ".jarvis" / "logs"), "/tmp/jarvis"]
    for cand in candidates:
        if not cand:
            continue
        p = Path(cand)
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".write_test"
            probe.touch()
            probe.unlink()
            return p
        except OSError:
            continue
    return Path("/tmp")


log_dir = _resolve_log_dir()

_handlers = [logging.StreamHandler(sys.stdout)]
try:
    _handlers.append(logging.FileHandler(log_dir / "jarvis.log"))
except OSError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_handlers,
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
        self.heartbeat = get_heartbeat(self.config)
        self._loop = None                    # asyncio loop, set in post_init
        self._bot = None                     # telegram bot, set in post_init

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
        app.add_handler(CommandHandler("device", self.cmd_device))
        app.add_handler(CommandHandler("nim", self.cmd_nim))
        app.add_handler(CommandHandler("deps", self.cmd_deps))
        app.add_handler(CommandHandler("heartbeat", self.cmd_heartbeat))
        app.add_handler(CommandHandler("mission", self.cmd_mission))
        app.add_handler(CommandHandler("work", self.cmd_work))
        app.add_handler(CommandHandler("journal", self.cmd_journal))
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
            "/device — Hardware & GPU info\n"
            "/nim — NVIDIA NIM status / switch model\n"
            "/deps — Dependency health\n"
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

    async def cmd_device(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detected hardware."""
        if not self._is_authorized(update.effective_user.id):
            return
        from .platform_detect import device
        dev = device()
        gpu = dev.gpu
        gpu_line = "none (CPU only)"
        if gpu.available:
            gpu_line = gpu.name or gpu.vendor
            if gpu.count > 1:
                gpu_line += f" x{gpu.count}"
            if gpu.memory_mb:
                gpu_line += f" · {gpu.memory_mb} MB"
            if gpu.cuda_version:
                gpu_line += f" · CUDA {gpu.cuda_version}"
        await update.message.reply_text(
            f"*Device*\n\n"
            f"OS: `{dev.os_name}`\n"
            f"Arch: `{dev.arch}`\n"
            f"Python: `{dev.python_version}`\n"
            f"CPU/RAM: `{dev.cpu_count} cores · {dev.memory_gb} GB`\n"
            f"Disk free: `{dev.disk_free_gb} GB`\n"
            f"GPU: `{gpu_line}`\n"
            f"Accelerator: `{dev.accelerator}`\n"
            f"Install target: `{dev.pip_target}`",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_nim(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """NVIDIA NIM status, or switch model with /nim <model-id>."""
        if not self._is_authorized(update.effective_user.id):
            return
        from . import nim as nimmod

        args = context.args or []
        cfg = nimmod.NIMConfig.from_env()

        if args:
            cfg.model = args[0]
            cfg.apply_to_env()
            self.config.llm_model = cfg.litellm_model
            await update.message.reply_text(
                f"NIM model set to `{cfg.model}`", parse_mode=ParseMode.MARKDOWN)
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        check = nimmod.validate_key(cfg)
        icon = "OK" if check.ok else "FAIL"
        await update.message.reply_text(
            f"*NVIDIA NIM — {icon}*\n\n"
            f"Mode: `{cfg.mode}`\n"
            f"Endpoint: `{cfg.api_base}`\n"
            f"Model: `{cfg.model}`\n"
            f"Key: `{cfg.masked_key()}`\n"
            f"Status: {check.message}\n"
            f"Latency: `{check.latency_ms} ms`\n\n"
            f"_Switch model:_ `/nim meta/llama-3.1-8b-instruct`",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_deps(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Dependency health; /deps install to fix missing ones."""
        if not self._is_authorized(update.effective_user.id):
            return
        from . import deps as depmod

        args = context.args or []
        if args and args[0] == "install":
            await update.message.reply_text("Installing missing dependencies...")
            statuses, results = depmod.ensure(auto=True)
            failed = [r.spec for r in results if not r.ok]
            if not results:
                await update.message.reply_text("Nothing to install.")
            elif failed:
                await update.message.reply_text(f"Failed: {', '.join(failed)}")
            else:
                await update.message.reply_text(
                    f"Installed {len(results)} package(s). Use /restart to reload.")
            return

        statuses = depmod.check_all()
        lines = []
        for s_ in statuses:
            mark = "OK  " if s_.satisfied else ("opt " if s_.req.optional else "MISS")
            lines.append(f"{mark} {s_.req.dist:<22} {s_.version or s_.reason}")
        gaps = depmod.missing(statuses)
        footer = ("\n\nAll good." if not gaps
                  else f"\n\n{len(gaps)} missing — send /deps install")
        await update.message.reply_text(
            "```\n" + "\n".join(lines) + "\n```" + footer,
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_heartbeat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Heartbeat daemon status; /heartbeat run <task> to fire a task now."""
        if not self._is_authorized(update.effective_user.id):
            return

        args = context.args or []
        if args and args[0] == "run":
            if len(args) < 2:
                names = ", ".join(self.heartbeat.tasks)
                await update.message.reply_text(f"Usage: /heartbeat run <task>\nTasks: {names}")
                return
            name = args[1]
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            result = await asyncio.to_thread(self.heartbeat.run_task, name)
            mark = "✓" if result.ok else "✗"
            await update.message.reply_text(f"{mark} {name}: {result.summary or 'done'}")
            return

        await update.message.reply_text(
            "🫀 *Heartbeat*\n```\n" + format_status(self.heartbeat.status()) + "\n```",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_mission(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set/show/clear the standing mission for autonomous work.

        /mission                → show current mission
        /mission <text>         → set the mission
        /mission clear          → stop autonomous work
        """
        if not self._is_authorized(update.effective_user.id):
            return
        from . import autonomy

        text = " ".join(context.args or []).strip()
        if not text:
            mission = autonomy.get_mission()
            if mission:
                task = self.heartbeat.tasks.get("agent_work")
                every = int(task.interval // 60) if task else 60
                await update.message.reply_text(
                    f"🎯 *Current mission* (worked on every {every}m):\n\n{mission}\n\n"
                    f"_Change:_ `/mission <new text>` · _Stop:_ `/mission clear` · "
                    f"_Work now:_ `/work`",
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await update.message.reply_text(
                    "🎯 No mission set — autonomous work is idle.\n\n"
                    "Give me a standing mission and I'll work on it every "
                    "heartbeat cycle, even while you're away:\n"
                    "`/mission Keep the repo tests green and write missing docs`",
                    parse_mode=ParseMode.MARKDOWN,
                )
            return

        if text.lower() == "clear":
            autonomy.clear_mission()
            await update.message.reply_text("🎯 Mission cleared — autonomous work paused.")
            return

        autonomy.set_mission(text)
        await update.message.reply_text(
            f"🎯 Mission set:\n\n{text}\n\n"
            f"I'll work on this every heartbeat cycle and report back. "
            f"Use /work to start a cycle right now.",
        )

    async def cmd_work(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Run an autonomous work cycle immediately."""
        if not self._is_authorized(update.effective_user.id):
            return
        from . import autonomy

        if not autonomy.get_mission():
            await update.message.reply_text(
                "🎯 No mission set. Set one first: `/mission <what to work on>`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        await update.message.reply_text("🛠 Starting a work cycle…")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        result = await asyncio.to_thread(self.heartbeat.run_task, "agent_work")
        mark = "✓" if result.ok else "✗"
        for chunk in self._chunk_message(f"{mark} {result.summary or 'done'}", 4000):
            await update.message.reply_text(chunk)

    async def cmd_journal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show the tail of the autonomous work journal."""
        if not self._is_authorized(update.effective_user.id):
            return
        from . import autonomy

        tail = autonomy.read_journal(3000)
        await update.message.reply_text(
            "📓 *Work journal* (recent)\n```\n" + tail[-3800:] + "\n```",
            parse_mode=ParseMode.MARKDOWN,
        )

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

    # ── Heartbeat wiring ───────────────────────────────────

    def _heartbeat_alert(self, task_name: str, message: str):
        """Called from the heartbeat thread — forwards alerts to the owner."""
        chat_id = self.owner_id or next(iter(self.authorized_users), None)
        if not (chat_id and self._bot and self._loop):
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self._bot.send_message(chat_id=chat_id, text=f"🫀 {message}"),
                self._loop,
            )
        except Exception as e:
            logger.error(f"Failed to deliver heartbeat alert: {e}")

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
            BotCommand("device", "Hardware & GPU info"),
            BotCommand("nim", "NVIDIA NIM status"),
            BotCommand("deps", "Dependency health"),
            BotCommand("reset", "Reset conversation"),
            BotCommand("inspect", "Self-inspect code"),
            BotCommand("diff", "Show changes"),
            BotCommand("rollback", "Undo last edit"),
            BotCommand("model", "Change LLM model"),
            BotCommand("shell", "Run shell command"),
            BotCommand("log", "View recent logs"),
            BotCommand("restart", "Restart service"),
            BotCommand("heartbeat", "Heartbeat daemon status"),
            BotCommand("mission", "Set/show autonomous work mission"),
            BotCommand("work", "Run a work cycle now"),
            BotCommand("journal", "Autonomous work journal"),
        ])
        logger.info("Bot commands registered")

        # start the heartbeat daemon alongside the bot
        jarvis._loop = asyncio.get_running_loop()
        jarvis._bot = application.bot
        if heartbeat_enabled():
            jarvis.heartbeat.on_alert(jarvis._heartbeat_alert)
            jarvis.heartbeat.start()
        else:
            logger.info("Heartbeat disabled (JARVIS_HEARTBEAT_ENABLED=0)")

    app.post_init = post_init

    logger.info("✅ JARVIS online — polling Telegram")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
