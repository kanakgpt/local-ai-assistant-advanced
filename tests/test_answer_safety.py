import unittest
from unittest.mock import patch

from app.services.answer import answer_question
from app.services.evaluate import score_answer
from app.services.rag import chunks


class AnswerSafetyTests(unittest.TestCase):
    def test_no_evidence_returns_abstention_without_generating_answer(self):
        with (
            patch("app.services.answer.search_docs", return_value=[]),
            patch("app.services.answer.search_web", return_value=[]),
            patch("app.services.answer.chat") as chat,
        ):
            result = answer_question("What does the document say?")

        self.assertEqual(result["sources"], [])
        self.assertEqual(result["evaluation"]["label"], "Unverified")
        self.assertIn("can't answer", result["answer"])
        chat.assert_not_called()

    def test_web_failure_is_explicit_in_retrieval_note(self):
        with (
            patch("app.services.answer.search_docs", return_value=[]),
            patch(
                "app.services.answer.search_web",
                return_value=[{"error": "Web search is currently unavailable."}],
            ),
        ):
            result = answer_question("What does the document say?")

        self.assertIn("Web search failed", result["retrieval_note"])
        self.assertEqual(result["used_web"], False)

    def test_insufficient_local_evidence_abstains_when_web_is_disabled(self):
        with (
            patch(
                "app.services.answer.search_docs",
                return_value=[{"text": "Weakly related text", "source": "guide.pdf", "page": 1}],
            ),
            patch("app.services.answer.json_chat", return_value={"sufficient": False}),
            patch("app.services.answer.chat") as chat,
        ):
            result = answer_question("What does the document say?", allow_web=False)

        self.assertIn("can't answer", result["answer"])
        self.assertIn("guide.pdf", result["sources"][0]["title"])
        self.assertIn("Web search is disabled", result["retrieval_note"])
        chat.assert_not_called()

    def test_invalid_question_is_rejected(self):
        with self.assertRaises(ValueError):
            answer_question(" ")

    def test_invalid_evaluator_output_is_marked_unverified(self):
        with patch("app.services.evaluate.json_chat", return_value={"score": "unknown"}):
            result = score_answer("question", "answer", [{"text": "source text"}])

        self.assertEqual(result["score"], 0)
        self.assertEqual(result["label"], "Unverified")

    def test_chunk_parameters_are_validated(self):
        with self.assertRaises(ValueError):
            chunks("text", size=10, overlap=10)


if __name__ == "__main__":
    unittest.main()
