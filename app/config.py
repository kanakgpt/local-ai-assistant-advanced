import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:3b")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
CHROMA_PATH = Path(os.getenv("CHROMA_PATH", str(DATA / "chroma_db")))
DOCS_PATH = Path(os.getenv("DOCUMENTS_PATH", str(DATA / "documents")))


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return value


TOP_K = _positive_int("TOP_K", 4)
MAX_UPLOAD_BYTES = _positive_int("MAX_UPLOAD_BYTES", 10 * 1024 * 1024)
MAX_PDF_PAGES = _positive_int("MAX_PDF_PAGES", 500)
MAX_EXTRACTED_CHARS = _positive_int("MAX_EXTRACTED_CHARS", 5_000_000)
CHROMA_PATH.mkdir(parents=True, exist_ok=True)
DOCS_PATH.mkdir(parents=True, exist_ok=True)
