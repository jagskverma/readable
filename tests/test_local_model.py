import unittest
from unittest.mock import patch

from helper import local_model


class LocalModelTests(unittest.TestCase):
    @patch.object(local_model, "request")
    def test_installed_cloud_model_is_refused_before_inference(self, request):
        request.return_value = {"models": [{"name": "hidden-cloud-model:latest", "remote_host": "https://example.com"}]}
        with self.assertRaisesRegex(RuntimeError, "downloaded Ollama model"):
            local_model.validate_model("hidden-cloud-model:latest")
        request.assert_called_once_with("/api/tags")

    @patch.object(local_model, "request")
    def test_output_keeps_unchanged_and_rewritten_slots_in_order(self, request):
        request.return_value = {"done": True, "message": {"content": '{"0":["keep","clearer"],"1":[" "]}'}}
        blocks = [{"slots": ["keep", "edit"]}, {"slots": ["original"]}]
        self.assertEqual(list(local_model.rewrite(blocks, "test-model")),
                         [(0, ["keep", "clearer"]), (1, ["original"])])

    @patch.object(local_model, "request")
    def test_partial_output_fails_before_any_paragraph_is_applied(self, request):
        request.return_value = {"done": True, "message": {"content": '{"0":["new"],"1":[]}'}}
        blocks = [{"slots": ["old"]}, {"slots": ["also old"]}]
        with self.assertRaisesRegex(ValueError, "Wrong number"):
            next(local_model.rewrite(blocks, "test-model"))
