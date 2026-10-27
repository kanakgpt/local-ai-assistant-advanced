import logging
from urllib.parse import urlsplit

from ddgs import DDGS

logger = logging.getLogger(__name__)


def search_web(query, max_results=5):
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("Search query must contain 1–2000 characters.")
    if not isinstance(max_results, int) or isinstance(max_results, bool) or max_results < 1:
        raise ValueError("max_results must be a positive integer.")

    results = []
    try:
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=min(max_results, 10)):
                candidate_url = item.get("href") or item.get("url") or ""
                parsed_url = urlsplit(candidate_url)
                safe_url = (
                    candidate_url[:2048]
                    if parsed_url.scheme in {"http", "https"} and parsed_url.netloc
                    else ""
                )
                results.append(
                    {
                        "title": str(item.get("title") or "Web result")[:300],
                        "url": safe_url,
                        "snippet": str(item.get("body") or item.get("snippet") or "")[:2000],
                    }
                )
    except Exception as exc:
        logger.warning("Web search failed: %s", type(exc).__name__)
        return [{"error": "Web search is currently unavailable."}]
    return results
