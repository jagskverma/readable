#!/bin/bash
set -eu
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
runner="$HOME/Library/Application Support/Readable/run-helper"
if [ ! -x "$runner" ]; then
  echo "Install Readable first with Install.command."
  exit 1
fi
if [ "$#" -gt 0 ]; then
  exec "$runner" use-local "$1"
fi

ollama_url="http://127.0.0.1:11434/api/version"
ollama_ready() {
  /usr/bin/curl --noproxy '*' --max-time 1 -fsS "$ollama_url" >/dev/null 2>&1
}
if ! ollama_ready && [ -d /Applications/Ollama.app ]; then
  /usr/bin/open -a Ollama || true
  for attempt in 1 2 3 4 5; do
    if ollama_ready; then break; fi
    sleep 1
  done
fi
if ! ollama_ready; then
  echo "Start Ollama and run setup again. Install Ollama from https://ollama.com/download/mac if needed."
  exit 1
fi

read -r -p "Ollama model [qwen3:4b]: " model || exit 1
model="${model:-qwen3:4b}"
if "$runner" use-local "$model"; then exit 0; fi
if [ "$model" != qwen3:4b ] || ! command -v ollama >/dev/null 2>&1; then
  printf 'Install the model in Ollama, then run setup again.\n'
  exit 1
fi
read -r -p 'Download the suggested qwen3:4b model (about 2.5 GB)? [y/N]: ' pull || exit 1
case "$pull" in
  y|Y|yes|YES)
    OLLAMA_HOST=127.0.0.1:11434 ollama pull qwen3:4b
    exec "$runner" use-local qwen3:4b
    ;;
  *) echo "Run setup again after downloading a local model."; exit 1 ;;
esac
