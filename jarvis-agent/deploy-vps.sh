#!/usr/bin/env bash
# JARVIS — VPS Deploy Script
#
# Sets up JARVIS as a systemd service on any Linux VPS.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/devvrat0209/my-agent/main/jarvis-agent/deploy-vps.sh | sudo bash
#
# Then edit /opt/jarvis/.env with your tokens and:
#   systemctl enable --now jarvis

set -euo pipefail

BOLD='\033[1m' CYAN='\033[36m' GREEN='\033[32m' RED='\033[31m' DIM='\033[2m' RESET='\033[0m'
die() { echo -e "${RED}${BOLD}✘ $*${RESET}" >&2; exit 1; }
info() { echo -e "${CYAN}➜ $*${RESET}"; }
ok() { echo -e "${GREEN}${BOLD}✔ $*${RESET}"; }

# Must be root
[ "$(id -u)" -eq 0 ] || die "Run as root: sudo bash deploy-vps.sh"

# ── Preflight ──────────────────────────────────────────────
command -v python3 >/dev/null || die "python3 required"
command -v git >/dev/null || { info "Installing git..."; apt-get install -y git >/dev/null 2>&1 || yum install -y git >/dev/null 2>&1; }
command -v systemctl >/dev/null || die "systemd required"

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
python3 -c "import sys; assert sys.version_info >= (3, 10)" 2>/dev/null || die "Python ≥ 3.10 required, got $PYTHON_VERSION"

# ── User & Paths ───────────────────────────────────────────
INSTALL_DIR="/opt/jarvis"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_USER="jarvis"

if ! id "$SERVICE_USER" &>/dev/null; then
  info "Creating system user: $SERVICE_USER"
  useradd --system --create-home --shell /bin/bash "$SERVICE_USER"
fi

# ── Clone ──────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
  info "Updating repo at $INSTALL_DIR"
  cd "$INSTALL_DIR" && git pull --ff-only 2>/dev/null || { info "Pull failed, re-cloning..."; rm -rf "$INSTALL_DIR" && git clone https://github.com/devvrat0209/my-agent.git "$INSTALL_DIR" --depth 1 && cd "$INSTALL_DIR"; }
else
  info "Cloning to $INSTALL_DIR"
  git clone https://github.com/devvrat0209/my-agent.git "$INSTALL_DIR" --depth 1
  cd "$INSTALL_DIR"
fi

AGENT_DIR="$INSTALL_DIR/jarvis-agent"
[ -d "$AGENT_DIR" ] || die "jarvis-agent/ not found"

# ── Venv & Install ─────────────────────────────────────────
info "Creating virtualenv..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

info "Installing JARVIS..."
pip install -e "$AGENT_DIR" --quiet

ok "Dependencies installed"

# ── .env ───────────────────────────────────────────────────
if [ ! -f "$INSTALL_DIR/.env" ]; then
  info "Creating .env template..."
  cat > "$INSTALL_DIR/.env" << 'ENVFILE'
# JARVIS Configuration — edit this file!

# LLM
JARVIS_LLM=openai/gpt-4o
OPENAI_API_KEY=sk-your-key-here

# Telegram Bot Token (get from @BotFather)
JARVIS_TELEGRAM_TOKEN=your-bot-token-here

# Authorized Telegram user IDs (comma-separated)
# Get your ID by messaging @userinfobot
JARVIS_TELEGRAM_USERS=

# Log directory
JARVIS_LOG_DIR=/var/log/jarvis
ENVFILE
fi

# ── Log dir ────────────────────────────────────────────────
mkdir -p /var/log/jarvis
chown "$SERVICE_USER:$SERVICE_USER" /var/log/jarvis

# ── Permissions ────────────────────────────────────────────
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# ── Systemd ────────────────────────────────────────────────
info "Installing systemd service..."
cp "$AGENT_DIR/jarvis.service" /etc/systemd/system/jarvis.service
systemctl daemon-reload

ok "Service installed"

# ── Done ──────────────────────────────────────────────────
echo ""
ok "JARVIS deployed to $INSTALL_DIR"
echo ""
echo -e "${BOLD}  Next steps:${RESET}"
echo ""
echo -e "  1. Edit config:"
echo -e "     ${CYAN}nano $INSTALL_DIR/.env${RESET}"
echo ""
echo -e "  2. Start JARVIS:"
echo -e "     ${CYAN}systemctl enable --now jarvis${RESET}"
echo ""
echo -e "  3. Check status:"
echo -e "     ${CYAN}systemctl status jarvis${RESET}"
echo -e "     ${CYAN}journalctl -u jarvis -f${RESET}"
echo ""
echo -e "  4. Talk to your bot on Telegram! 🤖"
echo ""
