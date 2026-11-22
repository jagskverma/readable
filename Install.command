#!/bin/bash
set -eu
cd "$(dirname "$0")"
app="$HOME/Library/Application Support/Readable"
# Brave on macOS overrides native-host lookup to the default Chrome location.
# This is independent of the active Brave profile path.
hosts="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
if [ "$(uname -s)" != Darwin ]; then echo "This installer is for macOS."; exit 1; fi
python3 -c 'import sys; assert sys.version_info >= (3,9)' || { echo "Install Python 3.9 or newer, then retry."; exit 1; }
mkdir -p "$app" "$hosts"
chmod 700 "$app"
cp -R extension "$app/"
cp helper/host.py helper/local_model.py "$app/"
python3 -m venv "$app/venv"
"$app/venv/bin/python" -m pip install -r requirements.txt
python3 - "$app" "$hosts" "$(cat helper/extension-id)" <<'PY'
import json, pathlib, shlex, sys
app, hosts = map(pathlib.Path, sys.argv[1:3])
runner = app/'run-helper'
runner.write_text('#!/bin/sh\nexec '+shlex.quote(str(app/'venv/bin/python'))+' '+shlex.quote(str(app/'host.py'))+' "$@"\n')
runner.chmod(0o700)
(hosts/'local.readable.rewriter.json').write_text(json.dumps(dict(name='local.readable.rewriter',
  description='Readable rewrite helper', path=str(runner), type='stdio',
  allowed_origins=['chrome-extension://'+sys.argv[3]+'/'])))
PY
echo "In brave://extensions, enable Developer mode, click Load unpacked, then select:"
echo "$app/extension"
open -R "$app/extension"
echo "Then run Sign-in.command for ChatGPT or Use-local-model.command for Ollama."
