import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from app.services.rag import index_pdf


class RagSafetyTests(unittest.TestCase):
    def test_index_rejects_pdf_over_page_limit(self):
        reader = SimpleNamespace(pages=[object(), object()])
        with (
            patch("app.services.rag.PdfReader", return_value=reader),
            patch("app.services.rag.MAX_PDF_PAGES", 1),
        ):
            with self.assertRaises(ValueError):
                index_pdf(Path("book.pdf"))

    def test_index_rejects_extracted_text_over_limit(self):
        page = SimpleNamespace(extract_text=lambda: "four")
        reader = SimpleNamespace(pages=[page])
        with (
            patch("app.services.rag.PdfReader", return_value=reader),
            patch("app.services.rag.MAX_EXTRACTED_CHARS", 3),
        ):
            with self.assertRaises(ValueError):
                index_pdf(Path("book.pdf"))

    def test_index_embeds_before_replacing_existing_source(self):
        page = SimpleNamespace(extract_text=lambda: "A useful paragraph from the PDF.")
        reader = SimpleNamespace(pages=[page])
        collection = Mock()
        operations = Mock()
        embed = Mock(return_value=[[0.1, 0.2]])
        operations.attach_mock(embed, "embed")
        operations.attach_mock(collection.delete, "delete")
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "book.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 fixture")
            with (
                patch("app.services.rag.PdfReader", return_value=reader),
                patch("app.services.rag.embed", embed),
                patch("app.services.rag.collection", collection),
            ):
                result = index_pdf(pdf_path, source_name="book.pdf")

        self.assertEqual(result["chunks_indexed"], 1)
        embed.assert_called_once()
        collection.delete.assert_called_once_with(where={"source": "book.pdf"})
        self.assertLess(
            operations.mock_calls.index(call.embed(["A useful paragraph from the PDF."])),
            operations.mock_calls.index(call.delete(where={"source": "book.pdf"})),
        )
        collection.add.assert_called_once()
        self.assertEqual(collection.add.call_args.kwargs["metadatas"][0]["source"], "book.pdf")


if __name__ == "__main__":
    unittest.main()
