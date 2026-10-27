import hashlib
import chromadb
from pypdf import PdfReader
from app.config import CHROMA_PATH, MAX_EXTRACTED_CHARS, MAX_PDF_PAGES, TOP_K
from app.services.llm import embed

db = chromadb.PersistentClient(path=str(CHROMA_PATH))
collection = db.get_or_create_collection("knowledge_documents", metadata={"hnsw:space": "cosine"})


def chunks(text, size=1000, overlap=150):
    if size < 1 or overlap < 0 or overlap >= size:
        raise ValueError("Chunk size must be positive and overlap must be smaller than size.")
    text = " ".join(text.split())
    out, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        part = text[start:end].strip()
        if part:
            out.append(part)
        if end >= len(text):
            break
        start = end - overlap
    return out


def index_pdf(path, source_name=None):
    reader = PdfReader(str(path))
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError(f"PDF exceeds the {MAX_PDF_PAGES}-page limit.")
    source = source_name or path.name
    rows = []
    extracted_chars = 0
    for page_no, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        extracted_chars += len(text)
        if extracted_chars > MAX_EXTRACTED_CHARS:
            raise ValueError(f"PDF exceeds the {MAX_EXTRACTED_CHARS}-character text limit.")
        for chunk_no, part in enumerate(chunks(text)):
            rows.append({"text": part, "source": source, "page": page_no, "chunk": chunk_no})
    if not rows:
        return {"filename": source, "chunks_indexed": 0, "message": "No extractable text; scanned PDF may need OCR."}

    embedded_batches = []
    for start in range(0, len(rows), 32):
        batch = rows[start:start+32]
        vectors = embed([r["text"] for r in batch])
        if len(vectors) != len(batch):
            raise RuntimeError("Embedding service returned an unexpected number of vectors.")
        embedded_batches.append((start, batch, vectors))

    document_version = hashlib.sha256(path.read_bytes()).hexdigest()
    collection.delete(where={"source": source})
    for start, batch, vectors in embedded_batches:
        ids = [
            hashlib.sha256(
                f"{document_version}|{r['page']}|{r['chunk']}|{start+i}".encode()
            ).hexdigest()
            for i, r in enumerate(batch)
        ]
        collection.add(
            ids=ids,
            documents=[r["text"] for r in batch],
            embeddings=vectors,
            metadatas=[
                {"source": r["source"], "page": r["page"], "chunk": r["chunk"]}
                for r in batch
            ],
        )
    return {"filename": source, "chunks_indexed": len(rows), "message": "Indexing complete."}

def search_docs(query, top_k=TOP_K):
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("Search query must contain 1–2000 characters.")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise ValueError("top_k must be a positive integer.")
    count = collection.count()
    if count == 0:
        return []
    vector = embed([query])[0]
    result = collection.query(query_embeddings=[vector], n_results=min(top_k, 10, count),
                              include=["documents", "metadatas", "distances"])
    return [{"text": t, "source": m.get("source","unknown"), "page": m.get("page","?"),
             "distance": float(d)} for t,m,d in zip(result["documents"][0], result["metadatas"][0], result["distances"][0])]
