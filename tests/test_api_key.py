import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "helper"))
import api_key
import host


class ApiKeyTests(unittest.TestCase):
    @patch.object(api_key, "keychain")
    def test_key_comes_from_keychain(self, keychain):
        keychain.return_value = "fixture-key"
        self.assertEqual(api_key.authorization(), {"Authorization": "Bearer fixture-key"})
        keychain.assert_called_once_with("get_password")

    @patch.object(api_key, "keychain", return_value=None)
    def test_missing_key_requires_setup(self, _):
        with self.assertRaisesRegex(RuntimeError, "No OpenAI API key is saved"):
            api_key.authorization()

    @patch.object(host, "request")
    def test_api_rewrite_reuses_stream_parser_and_bounds_output(self, request):
        events = [
            {"type": "response.output_text.delta", "delta": '[0,{"0":"Turn the device on."}]\n'},
            {"type": "response.completed"},
        ]
        request.return_value = io.BytesIO(b"".join(b"data: " + json.dumps(e).encode() + b"\n" for e in events))
        headers = {"Authorization": "Bearer fixture-key"}
        self.assertEqual(list(host.rewrite([{"slots": ["Power up the device."]}], "gpt-5-mini", headers, byok=True)),
                         [(0, ["Turn the device on."])])
        endpoint, payload, sent_headers = request.call_args.args
        self.assertEqual(endpoint, "https://api.openai.com/v1/responses")
        self.assertIs(sent_headers, headers)
        self.assertFalse(payload["store"])
        self.assertEqual(payload["max_output_tokens"], 4096)
        self.assertTrue(request.call_args.kwargs["byok"])

    @patch.object(host.urllib.request, "build_opener")
    def test_api_error_does_not_expose_server_body(self, build_opener):
        opener = Mock()
        opener.open.side_effect = HTTPError(host.API, 401, "Unauthorized", {}, io.BytesIO(b"fixture-key"))
        build_opener.return_value = opener
        with self.assertRaisesRegex(RuntimeError, "^OpenAI rejected the API key") as error:
            host.request(host.API + "/responses", byok=True)
        self.assertNotIn("fixture-key", str(error.exception))
