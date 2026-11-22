#!/bin/bash
set -eu
runner="$HOME/Library/Application Support/Readable/run-helper"
if [ ! -x "$runner" ]; then
  echo "Install Readable first with Install.command."
  exit 1
fi
if [ "$#" -gt 0 ]; then
  exec "$runner" use-local "$1"
fi
read -r -p "Installed Ollama model [qwen3:4b]: " model || exit 1
exec "$runner" use-local "${model:-qwen3:4b}"
