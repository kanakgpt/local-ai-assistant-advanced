import unittest
from unittest.mock import patch

from app.services.llm import json_chat


class LlmSafetyTests(unittest.TestCase):
    def test_json_chat_rejects_non_object_json(self):
        with patch("app.services.llm.chat", return_value='["not", "an object"]'):
            result = json_chat("system", "prompt")

        self.assertEqual(result, {})

    def test_json_chat_accepts_json_object_in_model_prose(self):
        with patch("app.services.llm.chat", return_value='Result: {"sufficient": false}'):
            result = json_chat("system", "prompt")

        self.assertEqual(result, {"sufficient": False})


if __name__ == "__main__":
    unittest.main()
