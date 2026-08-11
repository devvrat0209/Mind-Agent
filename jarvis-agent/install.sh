#!/usr/bin/env bash
# JARVIS Self-Editing AI Agent — One-Line Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/devvrat0209/my-agent/main/jarvis-agent/install.sh | bash

set -euo pipefail

BOLD='\033[1m'
CYAN='\033[36m'
GREEN='\033[32m'
RED='\033[31m'
DIM='\033[2m'
RESET='\033[0m'

jarvis_logo() {
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
}

die() { echo -e "${RED}${BOLD}✘ $*${RESET}" >&2; exit 1; }
info() { echo -e "${CYAN}➜ $*${RESET}"; }
ok() { echo -e "${GREEN}${BOLD}✔ $*${RESET}"; }
dim() { echo -e "${DIM}  $*${RESET}"; }

# ── Preflight ──────────────────────────────────────────────
jarvis_logo
echo -e "${BOLD}  Just A Rather Very Intelligent System — Installer${RESET}\n"

command -v git >/dev/null 2>&1 || die "git is required"
command -v python3 >/dev/null 2>&1 || die "python3 is required"
command -v pip >/dev/null 2>&1 || die "pip is required"

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if python3 -c "import sys; assert sys.version_info >= (3, 10)" 2>/dev/null; then
  ok "Python $PYTHON_VERSION"
else
  die "Python ≥ 3.10 required, got $PYTHON_VERSION"
fi

# ── Install Dir ────────────────────────────────────────────
INSTALL_DIR="${JARVIS_HOME:-$HOME/.jarvis}"
REPO_URL="https://github.com/devvrat0209/my-agent.git"

if [ -d "$INSTALL_DIR" ] && [ -d "$INSTALL_DIR/.git" ]; then
  info "Updating existing install at $INSTALL_DIR"
  cd "$INSTALL_DIR"
  git pull --ff-only 2>/dev/null || { info "Pull failed, re-cloning..."; rm -rf "$INSTALL_DIR" && git clone "$REPO_URL" "$INSTALL_DIR" --depth 1 && cd "$INSTALL_DIR"; }
else
  info "Cloning to $INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR" --depth 1
  cd "$INSTALL_DIR"
fi

# jarvis-agent lives inside the my-agent repo
AGENT_DIR="$INSTALL_DIR/jarvis-agent"
if [ ! -d "$AGENT_DIR" ]; then
  die "jarvis-agent/ not found in repo at $INSTALL_DIR"
fi
cd "$AGENT_DIR"

# ── Install ───────────────────────────────────────────────
info "Installing dependencies..."
if pip install -e . --break-system-packages --quiet 2>/dev/null; then
  ok "Installed"
elif pip install -e . --quiet 2>/dev/null; then
  ok "Installed"
else
  die "pip install failed. Run manually: cd $AGENT_DIR && pip install -e ."
fi

# ── Shell Hook ─────────────────────────────────────────────
SHELL_RC=""
if [ -n "${ZSH_VERSION:-}" ]; then SHELL_RC="$HOME/.zshrc"
elif [ -n "${BASH_VERSION:-}" ]; then SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ] && ! grep -q 'JARVIS_HOME' "$SHELL_RC" 2>/dev/null; then
  echo '' >> "$SHELL_RC"
  echo '# JARVIS AI Agent' >> "$SHELL_RC"
  echo "export JARVIS_HOME=\"$INSTALL_DIR\"" >> "$SHELL_RC"
  dim "Added JARVIS_HOME to $SHELL_RC"
fi

# ── Done ──────────────────────────────────────────────────
echo ""
ok "JARVIS is ready."
echo ""
echo -e "${BOLD}  Next steps:${RESET}"
echo -e "  1. Set your LLM:"
echo -e "     ${CYAN}export JARVIS_LLM=openai/gpt-4o${RESET}"
echo -e "     ${CYAN}export OPENAI_API_KEY=sk-...${RESET}"
echo ""
echo -e "     ${DIM}# Or Anthropic:${RESET}"
echo -e "     ${CYAN}export JARVIS_LLM=anthropic/claude-sonnet-4-20250514${RESET}"
echo -e "     ${CYAN}export ANTHROPIC_API_KEY=sk-ant-...${RESET}"
echo ""
echo -e "     ${DIM}# Or Ollama (local, free):${RESET}"
echo -e "     ${CYAN}ollama pull llama3 && export JARVIS_LLM=ollama/llama3${RESET}"
echo ""
echo -e "  2. Run it:"
echo -e "     ${CYAN}${BOLD}jarvis${RESET}"
echo ""
