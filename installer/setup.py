"""Install Readable into the current macOS user's Application Support."""

import base64
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

HOST = "local.readable.rewriter"
PROJECT = Path(__file__).resolve().parents[1]


def atomic_write(path, text, mode):
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as temp:
        saved = Path(temp.name)
        try:
            temp.write(text)
            temp.flush()
            saved.chmod(mode)
            saved.replace(path)
        finally:
            saved.unlink(missing_ok=True)


def install(project, home):
    extension = project / "extension"
    public_key = json.loads((extension / "manifest.json").read_text())["key"]
    digest = hashlib.sha256(base64.b64decode(public_key, validate=True)).hexdigest()
    extension_id = digest[:32].translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))
    if extension_id != (project / "helper" / "extension-id").read_text().strip():
        raise ValueError("The Readable extension and helper IDs do not match.")

    support = home / "Library/Application Support"
    app = support / "Readable"
    # Chrome and Brave use this native-host lookup directory on macOS.
    hosts = support / "Google/Chrome/NativeMessagingHosts"
    app.mkdir(mode=0o700, parents=True, exist_ok=True)
    app.chmod(0o700)
    hosts.mkdir(parents=True, exist_ok=True)

    python = app / "venv/bin/python"
    requirements = project / "requirements.txt"
    stamp = app / "venv/requirements.sha256"
    expected = hashlib.sha256(requirements.read_bytes()).hexdigest()
    ready = (
        python.is_file()
        and stamp.is_file()
        and stamp.read_text() == expected
        and subprocess.run(
            [str(python), "-I", "-c", "import jwt, cryptography, keyring"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
    )
    if not ready:
        subprocess.run([sys.executable, "-m", "venv", str(app / "venv")], check=True)
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(requirements)], check=True)
        atomic_write(stamp, expected, 0o600)

    shutil.copytree(extension, app / "extension", dirs_exist_ok=True)
    for file in ("host.py", "local_model.py", "api_key.py", "api_providers.py"):
        shutil.copy2(project / "helper" / file, app / file)

    runner = app / "run-helper"
    command = shlex.join([str(python), str(app / "host.py")])
    atomic_write(runner, f'#!/bin/sh\nexec {command} "$@"\n', 0o700)

    manifest = {
        "name": HOST,
        "description": "Readable rewrite helper",
        "path": str(runner),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }
    atomic_write(hosts / f"{HOST}.json", json.dumps(manifest, indent=2) + "\n", 0o644)
    return app / "extension"


if __name__ == "__main__":
    try:
        install(PROJECT, Path.home())
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        sys.exit(f"Readable setup failed: {exc}")
