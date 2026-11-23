import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "helper"))
import api_key
import api_providers as providers


class ApiKeyTests(unittest.TestCase):
    @patch.object(api_key, "keychain", return_value="fixture-key")
    def test_legacy_openai_settings_and_keychain_entry(self, keychain):
        provider = providers.from_settings({"backend": "openai-api", "model": "gpt-5-mini"})
        self.assertEqual(api_key.authorization(provider), {"Authorization": "Bearer fixture-key"})
        keychain.assert_called_once_with("get_password", "OpenAI API key")

    @patch.object(api_key, "keychain", return_value=None)
    def test_missing_provider_key_requires_setup(self, keychain):
        with self.assertRaisesRegex(RuntimeError, "No DeepSeek API key"):
            api_key.authorization(providers.PRESETS["deepseek"])
        keychain.assert_called_once_with("get_password", "DeepSeek API key")

    @patch.object(api_key, "keychain")
    def test_keyless_loopback_does_not_read_keychain(self, keychain):
        provider = providers.custom_provider("http://127.0.0.1:1234/v1", "chat", "none")
        self.assertEqual(api_key.authorization(provider), {})
        keychain.assert_not_called()

    def test_custom_keys_are_scoped_to_url_and_authentication_method(self):
        first = providers.custom_provider("https://EXAMPLE.test:443/v1/", "responses", "bearer")
        same = providers.custom_provider("https://example.test/v1", "chat", "bearer")
        self.assertEqual(first.key_account, same.key_account)
        for url, auth in (("https://other.test/v1", "bearer"), ("https://example.test/other", "bearer"),
                          ("https://example.test/v1", "api-key")):
            self.assertNotEqual(first.key_account, providers.custom_provider(url, "responses", auth).key_account)

    def test_unsafe_custom_endpoints_are_rejected(self):
        for url, auth in (("http://example.test/v1", "bearer"), ("https://example.test/v1", "none"),
                          ("https://user:secret@example.test/v1", "bearer"), ("https://example.test/v1?key=x", "bearer"),
                          ("https://example.test/v1/chat/completions", "bearer"), ("http://localhost.evil.test/v1", "none")):
            with self.subTest(url=url), self.assertRaises(ValueError):
                providers.custom_provider(url, "chat", auth)

    @patch.object(providers, "build_opener")
    def test_api_error_does_not_expose_server_body(self, build_opener):
        provider = providers.PRESETS["openai"]
        opener = Mock()
        opener.open.side_effect = HTTPError(provider.endpoint, 401, "Unauthorized", {}, io.BytesIO(b"fixture-key"))
        build_opener.return_value = opener
        with self.assertRaisesRegex(RuntimeError, "^OpenAI rejected the API key") as error:
            providers.request(provider, {}, {})
        self.assertNotIn("fixture-key", str(error.exception))

    def test_openai_payload_still_bounds_generation_and_storage(self):
        provider = providers.PRESETS["openai"]
        data = providers.payload_for(provider, provider.default_model, "instructions", "input")
        self.assertFalse(data["store"])
        self.assertTrue(data["stream"])
        self.assertEqual(data["max_output_tokens"], 4096)
        self.assertEqual(data["reasoning"], {"effort": "minimal"})
