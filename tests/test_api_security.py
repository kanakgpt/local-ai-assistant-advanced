import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class ApiSecurityTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.docs_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_chat_rejects_short_questions_and_unknown_fields(self):
        short = self.client.post("/api/chat", json={"question": " "})
        extra = self.client.post(
            "/api/chat", json={"question": "valid question", "unexpected": True}
        )

        self.assertEqual(short.status_code, 422)
        self.assertEqual(extra.status_code, 422)

    def test_chat_rejects_non_boolean_web_setting(self):
        response = self.client.post(
            "/api/chat", json={"question": "valid question", "allow_web": "false"}
        )

        self.assertEqual(response.status_code, 422)

    def test_chat_hides_internal_exception_details(self):
        with (
            patch("app.main.answer_question", side_effect=RuntimeError("secret detail")),
            self.assertLogs("app.main", level="ERROR") as server_log,
        ):
            response = self.client.post("/api/chat", json={"question": "valid question"})

        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret detail", response.text)
        self.assertIn("server logs", response.text)
        self.assertIn("secret detail", server_log.output[0])

    def test_upload_rejects_non_pdf_extension(self):
        response = self.client.post(
            "/api/documents/upload",
            files={"file": ("notes.txt", b"not a PDF", "text/plain")},
        )

        self.assertEqual(response.status_code, 400)

    def test_upload_rejects_invalid_pdf_content(self):
        with patch("app.main.DOCS_PATH", self.docs_path):
            response = self.client.post(
                "/api/documents/upload",
                files={"file": ("notes.pdf", b"not a PDF", "application/pdf")},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.docs_path.iterdir()), [])

    def test_upload_rejects_malformed_pdf_with_pdf_signature(self):
        with patch("app.main.DOCS_PATH", self.docs_path):
            response = self.client.post(
                "/api/documents/upload",
                files={"file": ("notes.pdf", b"%PDF-1.4\nnot a real PDF", "application/pdf")},
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(list(self.docs_path.iterdir()), [])

    def test_upload_enforces_configured_size_limit(self):
        with (
            patch("app.main.DOCS_PATH", self.docs_path),
            patch("app.main.MAX_UPLOAD_BYTES", 5),
        ):
            response = self.client.post(
                "/api/documents/upload",
                files={"file": ("notes.pdf", b"%PDF-1.4 larger than limit", "application/pdf")},
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(list(self.docs_path.iterdir()), [])

    def test_upload_sanitizes_client_filename_and_indexes_file(self):
        with (
            patch("app.main.DOCS_PATH", self.docs_path),
            patch(
                "app.main.index_pdf",
                return_value={"filename": "trusted.pdf", "chunks_indexed": 1},
            ) as index_pdf,
        ):
            response = self.client.post(
                "/api/documents/upload",
                files={"file": ("../../trusted.pdf", b"%PDF-1.4 valid test fixture", "application/pdf")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["upload"], "trusted.pdf")
        self.assertTrue((self.docs_path / "trusted.pdf").is_file())
        index_pdf.assert_called_once()
        self.assertEqual(index_pdf.call_args.kwargs["source_name"], "trusted.pdf")

    def test_security_headers_are_present(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
