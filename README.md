# Local AI Knowledge Assistant

A locally hosted retrieval-augmented generation (RAG) assistant. It indexes text from PDF files, retrieves relevant passages, optionally searches the public web when local evidence is not sufficient, and asks a local Ollama model to answer with citations. A separate model-based evaluator estimates how well the answer is supported by the retrieved evidence.

> **Scope and safety:** This project is a local, single-user reference application. It has no user authentication, authorization, tenant isolation, or production deployment hardening. Keep it bound to loopback (`127.0.0.1`). Do not expose it directly to the internet or an untrusted network. A model-generated answer or score is not a guarantee of truth.

## Contents

- [How it works](#how-it-works)
- [Components](#components)
- [Requirements](#requirements)
- [Setup on Windows](#setup-on-windows)
- [Configuration](#configuration)
- [Using the application](#using-the-application)
- [HTTP API](#http-api)
- [MCP tools](#mcp-tools)
- [Security and privacy](#security-and-privacy)
- [Hallucination controls and limitations](#hallucination-controls-and-limitations)
- [Testing](#testing)
- [Project layout](#project-layout)
- [Troubleshooting](#troubleshooting)

## How it works

1. **Upload:** The browser sends a PDF to the FastAPI backend. The backend checks the extension, normalizes the client-supplied filename, verifies the PDF signature, and enforces a configurable byte limit.
2. **Extract:** PyPDF extracts text from each page. The backend rejects files over the configured page or extracted-text limit. Scanned/image-only documents need OCR, which is not included.
3. **Chunk and embed:** Extracted text is split into overlapping chunks. Ollama creates embeddings with the configured embedding model.
4. **Index:** Chunks, embeddings, source names, and page numbers are persisted in a local ChromaDB collection.
5. **Retrieve:** A question is embedded and the nearest passages are retrieved from ChromaDB.
6. **Check evidence:** Ollama makes a conservative sufficiency assessment. If local evidence is not sufficient and web fallback is enabled, the application searches for a small number of public web snippets.
7. **Answer:** The answer model is instructed to use the retrieved data as untrusted reference material, cite its source labels, and state when the evidence is insufficient. If local evidence is judged insufficient and no web results are available (or web search is disabled), the application abstains without generating an answer.
8. **Evaluate:** A second model call estimates evidence support. This score is only an automated heuristic; it is not a calibrated probability or independent verification.

## Components

- **React + Vite frontend:** Chat interface, PDF upload, source display, web-fallback switch, and evaluator-score display.
- **FastAPI backend:** Chat and upload endpoints, validation, CORS allowlist, and security headers.
- **Ollama:** Local chat and embedding model runtime. Models must be installed locally.
- **ChromaDB:** Persistent local vector database stored under `data/chroma_db` by default.
- **PyPDF:** PDF text extraction.
- **DDGS:** Optional public web search. Search results are external, potentially stale, incomplete, or untrusted.
- **MCP server:** Optional stdio tools for local document search, public web search, and assistant Q&A.

## Requirements

- Windows 10/11 (commands below use PowerShell).
- Python 3.12 recommended.
- Node.js and npm.
- Ollama installed and running.
- Disk space for local models, PDFs, and the vector database.

## Setup on Windows

### 1. Install and start Ollama models

Install Ollama from its official distribution, start the Ollama service, then pull the default models:

```powershell
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

### 2. Create the Python environment and start the backend

Run these commands from the project root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If PowerShell prevents environment activation, either adjust the process-scoped execution policy or invoke `.\.venv\Scripts\python.exe` directly. Do not bind to `0.0.0.0` unless a separately secured deployment is intentionally configured.

### 3. Start the frontend

In another terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`. FastAPI's interactive API documentation is at `http://127.0.0.1:8000/docs`.

### 4. First question

Upload a text-based PDF, wait for indexing to complete, then ask a question. Web fallback is enabled by default in the UI and can be disabled for local-only retrieval.

## Configuration

Configuration is read from environment variables when the backend starts:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_CHAT_MODEL` | `qwen2.5:3b` | Ollama model used to generate and evaluate answers. |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Ollama model used for document and question embeddings. |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL. |
| `CHROMA_PATH` | `data/chroma_db` | Persistent ChromaDB directory. |
| `DOCUMENTS_PATH` | `data/documents` | Directory for successfully uploaded PDFs. |
| `TOP_K` | `4` | Default maximum number of local passages retrieved; search is capped at 10. |
| `MAX_UPLOAD_BYTES` | `10485760` (10 MiB) | Maximum accepted PDF upload size. |
| `MAX_PDF_PAGES` | `500` | Maximum accepted number of PDF pages. |
| `MAX_EXTRACTED_CHARS` | `5000000` | Maximum extracted text characters per PDF. |

The numeric limits must be positive integers. Restart the backend after changing an environment variable. Use absolute paths when relocating the database or document directory.

## Using the application

- **Upload PDF:** Accepts a `.pdf` file. Scanned documents without an embedded text layer return zero indexed chunks and require OCR performed separately.
- **Ask a question:** Questions must be 2–2000 characters. Additional/unknown JSON fields are rejected by the API.
- **Web fallback:** When enabled, search is attempted only if local evidence does not seem sufficient. The UI shows linked web sources when results are used.
- **Sources:** Each local result identifies the PDF and page. Web results include their title and URL. Always inspect the original source for important decisions.
- **Evaluation:** The numeric score indicates an LLM's assessment of evidence support, not correctness, confidence, or probability.

## HTTP API

### `GET /api/health`

Returns `{"status":"ok"}`. This indicates the API process is responsive; it does not verify Ollama or ChromaDB health.

### `POST /api/chat`

Request:

```json
{
  "question": "What does the uploaded guide say about dependency injection?",
  "allow_web": true
}
```

`question` is required and must contain 2–2000 characters. `allow_web` is an optional strict boolean. Unknown properties are rejected. Validation errors return HTTP 422. Unexpected assistant errors return a generic HTTP 500 response; details are logged by the backend, not disclosed in the response.

Successful responses contain:

- `answer`: generated response, or an abstention when no evidence was found.
- `sources`: retrieved PDF pages and/or web snippets.
- `used_web`: whether web results were included.
- `evaluation`: estimated evidence-support score, label, explanation, and limitations.
- `retrieval_note`: short note about evidence sufficiency and web fallback.

### `POST /api/documents/upload`

Multipart form field `file` must contain a PDF. The endpoint enforces the upload-size limit, filename normalization, and PDF signature check. Validation failures return 400, 413, or 422. Unexpected indexing errors return a generic 500 response and are recorded in server logs.

## MCP tools

Run from the project root with the same Python environment:

```powershell
.\.venv\Scripts\python.exe mcp_server.py
```

The server uses stdio transport. Configure it in the MCP client of your choice using that client's configuration format. It exposes:

- `search_local_documents(query, top_k=4)` — retrieve up to 10 indexed passages.
- `search_web_tool(query, max_results=5)` — search for up to 10 web results.
- `ask_knowledge_assistant(question, allow_web=true)` — run the same evidence-based answer flow.

MCP client and server must run in a trusted environment. These tools do not add authentication or tenant boundaries.

## Security and privacy

Implemented safeguards:

- Strict request schema and length/type checks.
- PDF extension, sanitized filename, signature, byte-size, page-count, and extracted-text limits.
- Temporary upload files are removed if processing fails.
- CORS is restricted to the two local Vite origins; credentials and wildcard methods/headers are disabled.
- Standard response headers reduce MIME sniffing, framing, referrer, and cache risks.
- Internal exception text is not returned to API clients; errors are logged server-side.
- Web and PDF passages are treated as untrusted data in model prompts.
- Search result counts and tool parameters are capped.

Operational boundaries:

- There is **no authentication, authorization, CSRF/session model, rate limiting, or multi-user isolation**. CORS is not authentication. Keep the server on loopback.
- If deploying beyond a trusted local machine, first add authentication/authorization, request and concurrency limits, TLS at a trusted proxy, per-user storage isolation, monitoring, and a deployment-specific threat review. Do not put an API secret into frontend code; browser-delivered secrets are public.
- Uploaded PDFs, extracted text, and embeddings are persisted locally. Protect the machine and its backups, and remove sensitive data using an appropriate operational process.
- The default Ollama endpoint is local. If `OLLAMA_HOST` points elsewhere, prompts and retrieved document context are sent to that endpoint.
- Web fallback sends the user's query to the configured public search provider. Disable it for private questions or offline use.
- PDF parsing and local model execution consume CPU, memory, and disk. Limits reduce exposure but do not replace process-level resource limits or isolation.

## Hallucination controls and limitations

The application reduces—but cannot eliminate—unsupported output:

- It abstains before generation when evidence is absent or local evidence is judged insufficient without usable web results.
- It asks the sufficiency evaluator to be conservative and to treat passages as data, not instructions.
- The generation prompt asks for exact source labels and supported claims only.
- An evaluator explains its heuristic score and includes a non-probability limitation.

These are prompt-based controls, not formal guarantees. Models can still misread sources, follow prompt injections, omit citations, or produce incorrect answers and scores. The sufficiency and evaluation calls are also model outputs. Web snippets may be wrong or stale. Validate important answers against the cited PDF page or original web page; use a separately curated evaluation set and human review before relying on this system for consequential decisions.

## Testing

The backend tests use Python's standard `unittest` library and mock external model/search calls. From the project root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests cover API schema enforcement, safe error responses, upload extension/signature/size/name handling, response headers, evidence sufficiency and abstention, web failure and URL handling, evaluator/JSON-output failure handling, PDF processing limits, and chunk argument validation. They do not prove model factuality, Ollama integration, live web search behavior, load capacity, or production deployment security.

Build the frontend bundle from its directory with:

```powershell
Set-Location frontend
npm.cmd run build
```

The development server is started with `npm.cmd run dev`.

## Project layout

```text
app/
  config.py                 Environment configuration and local data paths
  main.py                   FastAPI app, chat and upload HTTP endpoints
  services/
    answer.py               Evidence selection, abstention, prompt construction
    evaluate.py             LLM-based evidence-support heuristic
    llm.py                  Ollama chat, JSON response, and embeddings
    rag.py                  PDF extraction, chunking, ChromaDB index/search
    web.py                  Optional external web search
data/
  documents/                Uploaded PDFs (default location)
  chroma_db/                Persistent vector database (default location)
frontend/
  src/App.jsx               React chat, upload, source, and score UI
  src/style.css             Frontend styling
mcp_server.py               Optional stdio MCP server and tools
requirements.txt            Python runtime dependencies
tests/                      Offline backend regression/security tests
README.md                   Setup, usage, architecture, and limitations
```

## Troubleshooting

- **Ollama connection error:** Confirm Ollama is running, verify `OLLAMA_HOST`, and check that both configured models have been pulled.
- **No local results:** Upload a text-based PDF and confirm the upload reports indexed chunks. Scanned PDFs need OCR; confirm the question uses terminology present in the document.
- **Web search unavailable:** Check network access. Local retrieval remains available, and the response notes failed web fallback.
- **Upload rejected:** Confirm the file is a valid PDF, is within the byte/page/text limits, and uses a `.pdf` extension.
- **Frontend cannot connect:** Start the backend on `127.0.0.1:8000`; the frontend currently targets that address.
- **Index/database errors:** Check that `CHROMA_PATH` and `DOCUMENTS_PATH` are writable and that sufficient disk space is available.
