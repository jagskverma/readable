#!/bin/bash
set -eu
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

app="$HOME/Library/Application Support/Readable"
runner="$app/run-helper"
mode="${1:-setup}"

case "$mode" in
  setup|--install-only|--configure) ;;
  *) echo "Usage: Install.command [--install-only | --configure]"; exit 2 ;;
esac
if [ "$(uname -s)" != Darwin ]; then
  echo "This installer is for macOS."
  exit 1
fi
if [ "$(id -u)" = 0 ]; then
  echo "Run setup as your regular macOS user, without sudo."
  exit 1
fi

printf 'Readable uses an eligible ChatGPT Plus or Pro plan by default. ChatGPT Free does not include rewrite usage.\n'
printf 'Local Ollama is optional and needs no ChatGPT plan. API keys are not supported in this release.\n'

# Make the provider choice before writing files on a fresh interactive setup.
choice=""
if [ "$mode" != --install-only ]; then
  if [ ! -t 0 ]; then
    echo "Run setup interactively to choose a provider, or pass --install-only to install the helper."
    exit 2
  fi
  if [ "$mode" = --configure ] || { [ ! -f "$app/settings.json" ] && [ ! -f "$app/session.json" ]; }; then
    printf '\nChoose how Readable should rewrite pages:\n  1. ChatGPT Plus or Pro (default)\n  2. Local Ollama model\n  3. Exit setup\n'
    read -r -p 'Choose [1, 2, or 3]: ' choice || exit 0
    case "$choice" in
      ''|1) choice=1 ;;
      2) ;;
      3) exit 0 ;;
      *) echo "Choose 1, 2, or 3."; exit 2 ;;
    esac
  fi
fi

if [ "$mode" != --configure ] || [ ! -x "$runner" ]; then
  python="$(command -v python3 || true)"
  if [ -z "$python" ] ||
     { [ "$python" = /usr/bin/python3 ] && ! /usr/bin/xcode-select -p >/dev/null 2>&1; } ||
     ! "$python" -I -c 'import sys, venv; assert sys.version_info >= (3, 9)' 2>/dev/null; then
    echo "Setup needs Python 3.9 or newer. Install it from https://www.python.org/downloads/macos/ and run setup again."
    exit 1
  fi
  "$python" installer/setup.py
  printf '\nReadable installed. In brave://extensions, turn on Developer mode and choose Load unpacked.\n'
  printf 'Select this folder, or use Cmd+Shift+G in the folder picker:\n%s\n' "$app/extension"
  printf 'If Readable is already in Brave, use Reload on its extension card.\n'
  if [ "$mode" = --install-only ] || [ ! -t 0 ]; then exit 0; fi
  /usr/bin/open -R "$app/extension" >/dev/null 2>&1 || true
  /usr/bin/open -a "Brave Browser" "brave://extensions/" >/dev/null 2>&1 || true
fi

case "$choice" in
  1) exec "$runner" login ;;
  2) exec /bin/bash ./installer/configure-ollama.sh ;;
  '') printf '\nYour existing provider is unchanged. Run Install.command --configure to change it.\n' ;;
esac
