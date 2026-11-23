"""Exercise the native host against real local HTTP connections, without API keys."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import select
import struct
import subprocess
import sys
from threading import Thread
import unittest

PROJECT = Path(__file__).resolve().parents[1]
BLOCKS = [{"slots": ["Power up the device.", "keep this"]}, {"slots": ["Original wording"]}]
OUTPUT = '[0,{"0":"Turn the device on."}]\n[1,{}]'

HOST = """
import dataclasses
import json
import sys
sys.path.insert(0, "helper")
import host
settings = json.loads(sys.argv[1])
base = sys.argv[2]
host.load = lambda name: settings
host.api_key.keychain = lambda op, account: "fixture-" + account
provider = settings.get("backend", "chatgpt")
if provider == "ollama":
    host.local_model.BASE_URL = base
elif provider == "chatgpt":
    host.API = base
    host.access = lambda: {"Authorization": "Bearer fixture-plan"}
elif settings.get("provider") != "custom":
    slug = settings.get("provider", "openai")
    item = host.api_providers.PRESETS[slug]
    host.api_providers.PRESETS[slug] = dataclasses.replace(item, base=base)
host.serve()
"""


def stream(path, output):
    if path.endswith("/responses"):
        events = ({"type": "response.output_text.delta", "delta": output[:12]},
                  {"type": "response.output_text.delta", "delta": output[12:]},
                  {"type": "response.completed"})
    elif path.endswith("/messages"):
        events = ({"type": "content_block_delta", "delta": {"type": "text_delta", "text": output}},
                  {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
                  {"type": "message_stop"})
    else:
        events = ({"choices": [], "usage": {}},
                  {"choices": [{"delta": {"reasoning_content": "private reasoning"}}]},
                  {"choices": [{"delta": {"content": output}, "finish_reason": "stop"}]})
    return b": keep-alive\n\n" + b"".join(b"data: " + json.dumps(event).encode() + b"\n\n" for event in events)


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, body, content_type="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/tags":
            self.send(b'{"models":[{"name":"fixture-model"}]}')
        else:
            self.send(b'{"models":[{"visibility":"list","slug":"fixture-model"}]}')

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.calls.append((self.path, dict(self.headers), payload))
        if self.path.startswith("/redirect"):
            self.send_response(307)
            self.send_header("Location", "/reforwarded")
            self.end_headers()
        elif self.path.endswith("/api/chat"):
            self.send(json.dumps({"done": True, "message": {"content": '{"0":["Turn the device on.","keep this"],"1":["Original wording"]}'}}).encode())
        elif self.path.startswith("/truncated"):
            self.send(b'data: {"type":"response.output_text.delta","delta":"[0,{}]"}\n\n', "text/event-stream")
        elif not payload["stream"]:
            self.send(json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": OUTPUT}}]}).encode())
        else:
            self.send(stream(self.path, OUTPUT), "text/event-stream")


class NativeProviderTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        self.server.calls = []
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def rewrite(self, settings):
        with subprocess.Popen([sys.executable, "-c", HOST, json.dumps(settings), self.base],
                              cwd=PROJECT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0) as proc:
            request = json.dumps({"batch": 7, "blocks": BLOCKS}).encode()
            proc.stdin.write(struct.pack("=I", len(request)) + request)
            proc.stdin.flush()
            output = []
            try:
                while True:
                    self.assertTrue(select.select([proc.stdout], [], [], 8)[0], "Native helper timed out")
                    header = proc.stdout.read(4)
                    if not header:
                        break
                    size, = struct.unpack("=I", header)
                    reply = json.loads(proc.stdout.read(size))
                    output.append(reply)
                    if reply.get("complete") or reply.get("error"):
                        break
            finally:
                proc.stdin.close()
            self.assertTrue(output, proc.stderr.read().decode())
            return output

    def successful(self, settings):
        self.assertEqual(self.rewrite(settings), [
            {"batch": 7, "block": 0, "texts": ["Turn the device on.", "keep this"]},
            {"batch": 7, "block": 1, "texts": ["Original wording"]},
            {"batch": 7, "complete": True},
        ])

    def test_all_presets(self):
        sys.path.insert(0, str(PROJECT / "helper"))
        from api_providers import PATHS, PRESETS
        for slug, provider in PRESETS.items():
            with self.subTest(provider=slug):
                self.successful({"backend": "api-key", "provider": slug, "model": "fixture-model"})
                path, headers, data = self.server.calls[-1]
                self.assertEqual(path, PATHS[provider.protocol])
                normalized = {key.lower(): value for key, value in headers.items()}
                expected = provider.headers("fixture-" + provider.key_account)
                self.assertEqual({key.lower(): normalized[key.lower()] for key in expected},
                                 {key.lower(): value for key, value in expected.items()})
                self.assertTrue(data["stream"])

    def test_legacy_openai_key(self):
        self.successful({"backend": "openai-api", "model": "fixture-model"})
        self.assertEqual(self.server.calls[-1][1]["Authorization"], "Bearer fixture-OpenAI API key")

    def test_chatgpt_plan_and_ollama(self):
        self.successful({})
        self.assertEqual(self.server.calls[-1][1]["Authorization"], "Bearer fixture-plan")
        self.successful({"backend": "ollama", "model": "fixture-model"})
        self.assertEqual(self.server.calls[-1][0], "/api/chat")

    def test_custom_azure_style_key_and_non_streaming_response(self):
        self.successful({"backend": "api-key", "provider": "custom", "model": "fixture",
                         "base_url": self.base + "/openai/v1", "auth": "api-key", "protocol": "chat-modern", "stream": False})
        path, headers, data = self.server.calls[-1]
        self.assertEqual(path, "/openai/v1/chat/completions")
        self.assertTrue(headers["Api-Key"].startswith("fixture-Custom API key "))
        self.assertEqual(data["max_completion_tokens"], 4096)

    def test_redirect_is_never_followed_with_a_key(self):
        output = self.rewrite({"backend": "api-key", "provider": "custom", "model": "fixture",
                               "base_url": self.base + "/redirect", "auth": "bearer", "protocol": "chat"})
        self.assertIn("redirected", output[-1]["error"])
        self.assertEqual(len(self.server.calls), 1)

    def test_truncation_is_not_reported_as_success(self):
        output = self.rewrite({"backend": "api-key", "provider": "custom", "model": "fixture",
                               "base_url": self.base + "/truncated", "auth": "none", "protocol": "responses"})
        self.assertIn("disconnected", output[-1]["error"])
        self.assertNotIn("Authorization", self.server.calls[-1][1])
