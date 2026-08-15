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

# ── Fetch ──────────────────────────────────────────────────
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

# ── Detect device ──────────────────────────────────────────
# platform_detect.py is stdlib-only, so it runs before anything is installed.
info "Detecting device..."
JARVIS_AGENT_DIR="$AGENT_DIR" python3 <<'PYDETECT' || true
import os
import sys

sys.path.insert(0, os.environ["JARVIS_AGENT_DIR"])
try:
    from jarvis.platform_detect import device

    d = device()
    g = d.gpu
    print(f"  System:      {d.os_name} ({d.arch})")
    print(f"  Python:      {d.python_version}")
    gpu = g.name or "none detected (CPU only)"
    if g.count > 1:
        gpu += f" x{g.count}"
    if g.cuda_version:
        gpu += f", CUDA {g.cuda_version}"
    print(f"  GPU:         {gpu}")
    print(f"  Accelerator: {d.accelerator}")
    print(f"  pip target:  {d.pip_target}")
except Exception as exc:
    print(f"  (detection skipped: {exc})")
PYDETECT
echo ""

# ── Install ────────────────────────────────────────────────
# Choose pip flags for this environment (venv / conda / PEP 668 / root).
PIP_FLAGS=""
if [ -n "${VIRTUAL_ENV:-}" ] || [ -n "${CONDA_PREFIX:-}" ]; then
  PIP_FLAGS=""
elif python3 -c "import os, sysconfig, sys; sys.exit(0 if os.path.exists(os.path.join(sysconfig.get_paths()['stdlib'], 'EXTERNALLY-MANAGED')) else 1)"; then
  PIP_FLAGS="--break-system-packages"
  if [ "$(id -u)" -ne 0 ]; then
    PIP_FLAGS="$PIP_FLAGS --user"
  fi
elif [ "$(id -u)" -ne 0 ]; then
  PIP_FLAGS="--user"
fi

info "Installing${PIP_FLAGS:+ ($PIP_FLAGS)}..."
# shellcheck disable=SC2086
pip install -e "$AGENT_DIR" $PIP_FLAGS --quiet 2>/dev/null \
  || pip install -e "$AGENT_DIR" --break-system-packages --quiet 2>/dev/null \
  || pip install -e "$AGENT_DIR" --quiet 2>/dev/null \
  || die "pip install failed"
ok "Installed"

# ── Verify ─────────────────────────────────────────────────
if command -v jarvis >/dev/null 2>&1; then
  ok "jarvis is on your PATH"
else
  echo -e "  ${DIM}jarvis isn't on PATH yet — try: export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
fi

# ── Done ───────────────────────────────────────────────────
echo ""
ok "Done!"
echo ""
echo -e "${BOLD}  Run:${RESET}"
echo -e "    ${CYAN}${BOLD}jarvis${RESET}"
echo ""
echo -e "  ${DIM}First run = setup wizard: device check, dependency install,${RESET}"
echo -e "  ${DIM}NVIDIA NIM, Telegram and REST API. After that = starts the bot.${RESET}"
echo ""
echo -e "${BOLD}  Other commands:${RESET}"
echo -e "    ${CYAN}jarvis doctor${RESET}    ${DIM}check device + dependencies + config${RESET}"
echo -e "    ${CYAN}jarvis install${RESET}   ${DIM}install missing dependencies${RESET}"
echo -e "    ${CYAN}jarvis api${RESET}       ${DIM}start the REST API${RESET}"
echo -e "    ${CYAN}jarvis nim test${RESET}  ${DIM}test the NVIDIA NIM connection${RESET}"
echo ""
