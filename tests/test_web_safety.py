import unittest
from unittest.mock import MagicMock, patch

from app.services.web import search_web


class WebSafetyTests(unittest.TestCase):
    def test_search_drops_non_http_source_urls_and_bounds_results(self):
        ddgs = MagicMock()
        ddgs.__enter__.return_value.text.return_value = [
            {"title": "Unsafe link", "href": "javascript:alert(1)", "body": "Snippet"},
            {"title": "Safe link", "href": "https://example.com", "body": "Snippet"},
        ]
        with patch("app.services.web.DDGS", return_value=ddgs):
            results = search_web("topic", max_results=100)

        self.assertEqual(results[0]["url"], "")
        self.assertEqual(results[1]["url"], "https://example.com")
        ddgs.__enter__.return_value.text.assert_called_once_with("topic", max_results=10)

    def test_search_rejects_empty_queries(self):
        with self.assertRaises(ValueError):
            search_web(" ")


if __name__ == "__main__":
    unittest.main()
