import logging
import re
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from pypdf.errors import PdfReadError

from app.config import DOCS_PATH, MAX_UPLOAD_BYTES
from app.services.rag import index_pdf
from app.services.answer import answer_question

logger = logging.getLogger(__name__)
app = FastAPI(
    title="Local AI Knowledge Assistant",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=2, max_length=2000)
    allow_web: StrictBool = True


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/chat")
def chat_endpoint(payload: ChatRequest):
    try:
        return answer_question(payload.question, payload.allow_web)
    except Exception as exc:
        logger.exception("Chat request failed")
        raise HTTPException(
            status_code=500,
            detail="The assistant could not complete the request. Check the server logs.",
        ) from exc


def _safe_pdf_filename(filename: str) -> str:
    basename = Path(filename.replace("\\", "/")).name
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", basename).lstrip(".")
    if not safe_name or not safe_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF file with a valid filename.")
    stem = safe_name[:-4].rstrip(".")[:251]
    if not stem:
        raise HTTPException(status_code=400, detail="Upload a PDF file with a valid filename.")
    return f"{stem}.pdf"

@app.post("/api/documents/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF file.")

    filename = _safe_pdf_filename(file.filename)
    temp_path = None
    try:
        DOCS_PATH.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=DOCS_PATH, prefix=".upload-", suffix=".pdf", delete=False
        ) as out:
            temp_path = Path(out.name)
            size = 0
            while chunk := await file.read(64 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"PDF exceeds the {MAX_UPLOAD_BYTES}-byte upload limit.",
                    )
                out.write(chunk)

        with temp_path.open("rb") as uploaded:
            if uploaded.read(5) != b"%PDF-":
                raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF.")

        try:
            result = index_pdf(temp_path, source_name=filename)
        except (PdfReadError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail="The PDF is malformed or exceeds configured processing limits.",
            ) from exc
        destination = DOCS_PATH / filename
        temp_path.replace(destination)
        temp_path = None
        return {"upload": filename, **result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("PDF upload or indexing failed")
        raise HTTPException(
            status_code=500,
            detail="Could not process the PDF. Check the server logs.",
        ) from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        await file.close()
