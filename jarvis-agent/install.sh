#!/usr/bin/env bash
# JARVIS — One-Line Install
#
# curl -fsSL https://raw.githubusercontent.com/devvrat0209/my-agent/main/jarvis-agent/install.sh | bash
#
# Then just run: jarvis

set -euo pipefail

BOLD='\033[1m' CYAN='\033[36m' GREEN='\033[32m' RED='\033[31m' DIM='\033[2m' RESET='\033[0m'

die() { echo -e "${RED}${BOLD}✘ $*${RESET}" >&2; exit 1; }
info() { echo -e "${CYAN}➜ $*${RESET}"; }
ok() { echo -e "${GREEN}${BOLD}✔ $*${RESET}"; }

echo -e "${CYAN}${BOLD}"
cat << 'EOF'
   ██╗ █████╗ ██████╗ █████╗ ██████╗ ██████╗ ██████╗
   ╚═╝██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔═══██╗██╔══██╗
      ██║  ██║██████╔╝███████║██║  ██║██║   ██║██████╔╝
      ██║  ██║██╔══██╗██╔══██║██║  ██║██║   ██║██╔═══╝
      ╚█████╔╝██║  ██║██║  ██║██████╔╝╚██████╔╝██║
       ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝  ╚═════╝ ╚═╝
EOF
echo -e "${RESET}"

echo -e "${BOLD}  Just A Rather Very Intelligent System — Installer${RESET}\n"

command -v git >/dev/null 2>&1 || die "git required"
command -v python3 >/dev/null 2>&1 || die "python3 required"

python3 -c "import sys; assert sys.version_info >= (3, 10)" 2>/dev/null || die "Python ≥ 3.10 required"

# ── Install ────────────────────────────────────────────────
INSTALL_DIR="${JARVIS_HOME:-$HOME/.jarvis}"
REPO_URL="https://github.com/devvrat0209/my-agent.git"
REPO_BRANCH="${JARVIS_BRANCH:-main}"

if [ -d "$INSTALL_DIR" ] && [ -d "$INSTALL_DIR/.git" ]; then
  info "Updating $INSTALL_DIR"
  cd "$INSTALL_DIR" && git pull --ff-only 2>/dev/null || { rm -rf "$INSTALL_DIR" && git clone --branch "$REPO_BRANCH" "$REPO_URL" "$INSTALL_DIR" --depth 1 && cd "$INSTALL_DIR"; }
else
  info "Cloning to $INSTALL_DIR"
  git clone --branch "$REPO_BRANCH" "$REPO_URL" "$INSTALL_DIR" --depth 1
  cd "$INSTALL_DIR"
fi

AGENT_DIR="$INSTALL_DIR/jarvis-agent"
[ -d "$AGENT_DIR" ] || die "jarvis-agent/ not found"

# ── Install ───────────────────────────────────────────────
info "Installing..."
pip install -e "$AGENT_DIR" --break-system-packages --quiet 2>/dev/null || pip install -e "$AGENT_DIR" --quiet 2>/dev/null || die "pip install failed"
ok "Installed"

# ── Done ──────────────────────────────────────────────────
echo ""
ok "Done!"
echo ""
echo -e "${BOLD}  Run:${RESET}"
echo -e "    ${CYAN}${BOLD}jarvis${RESET}"
echo ""
echo -e "  ${DIM}First run = setup wizard. After that = starts the bot.${RESET}"
echo ""
