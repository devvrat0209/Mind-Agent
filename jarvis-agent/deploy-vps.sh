#!/usr/bin/env bash
# JARVIS — VPS Deploy
#
# Usage: curl -fsSL https://raw.githubusercontent.com/devvrat0209/my-agent/main/jarvis-agent/deploy-vps.sh | sudo bash
#
# After this, just run: jarvis
# It'll walk you through setup on first run.

set -euo pipefail

BOLD='\033[1m' CYAN='\033[36m' GREEN='\033[32m' RED='\033[31m' DIM='\033[2m' RESET='\033[0m'
die() { echo -e "${RED}${BOLD}✘ $*${RESET}" >&2; exit 1; }
info() { echo -e "${CYAN}➜ $*${RESET}"; }
ok() { echo -e "${GREEN}${BOLD}✔ $*${RESET}"; }

[ "$(id -u)" -eq 0 ] || die "Run as root: sudo bash deploy-vps.sh"

# ── Preflight ──────────────────────────────────────────────
command -v python3 >/dev/null || die "python3 required"
command -v git >/dev/null || { info "Installing git..."; apt-get install -y git >/dev/null 2>&1 || yum install -y git >/dev/null 2>&1; }

python3 -c "import sys; assert sys.version_info >= (3, 10)" 2>/dev/null || die "Python ≥ 3.10 required"

# ── Install ────────────────────────────────────────────────
INSTALL_DIR="/opt/jarvis"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_USER="jarvis"

if ! id "$SERVICE_USER" &>/dev/null; then
  info "Creating user: $SERVICE_USER"
  useradd --system --create-home --shell /bin/bash "$SERVICE_USER"
fi

if [ -d "$INSTALL_DIR/.git" ]; then
  info "Updating repo..."
  cd "$INSTALL_DIR" && git pull --ff-only 2>/dev/null || { rm -rf "$INSTALL_DIR" && git clone https://github.com/devvrat0209/my-agent.git "$INSTALL_DIR" --depth 1 && cd "$INSTALL_DIR"; }
else
  info "Cloning repo..."
  git clone https://github.com/devvrat0209/my-agent.git "$INSTALL_DIR" --depth 1
  cd "$INSTALL_DIR"
fi

[ -d "$INSTALL_DIR/jarvis-agent" ] || die "jarvis-agent/ not found"

# ── Venv ──────────────────────────────────────────────────
info "Installing dependencies..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install -e "$INSTALL_DIR/jarvis-agent" --quiet
ok "Installed"

# ── Systemd ────────────────────────────────────────────────
info "Setting up service..."
cp "$INSTALL_DIR/jarvis-agent/jarvis.service" /etc/systemd/system/jarvis.service
systemctl daemon-reload
ok "Service installed"

# ── Permissions ────────────────────────────────────────────
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
mkdir -p /var/log/jarvis
chown "$SERVICE_USER:$SERVICE_USER" /var/log/jarvis

# ── Add to PATH ────────────────────────────────────────────
if ! grep -q '/opt/jarvis/venv/bin' /etc/environment 2>/dev/null; then
  echo 'PATH="/opt/jarvis/venv/bin:$PATH"' >> /etc/environment
fi
ln -sf "$VENV_DIR/bin/jarvis" /usr/local/bin/jarvis 2>/dev/null || true

# ── Done ──────────────────────────────────────────────────
echo ""
ok "JARVIS installed!"
echo ""
echo -e "${BOLD}  Run it:${RESET}"
echo -e "    ${CYAN}jarvis${RESET}"
echo ""
echo -e "  ${DIM}First run walks you through setup (tokens, model, etc).${RESET}"
echo -e "  ${DIM}After that, just 'jarvis' starts the bot.${RESET}"
echo ""
echo -e "  ${BOLD}Or as a service:${RESET}"
echo -e "    ${CYAN}sudo -u jarvis /opt/jarvis/venv/bin/jarvis${RESET}"
echo -e "    ${CYAN}systemctl enable --now jarvis${RESET}"
echo ""
