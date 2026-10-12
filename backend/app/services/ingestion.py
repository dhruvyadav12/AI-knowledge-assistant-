import logging
from pathlib import Path

from ..database import SessionLocal
from ..models import Document
from .chunking import chunk_pages
from .extraction import extract_text
from .vector_store import get_vector_store

log = logging.getLogger(__name__)


def ingest_document(document_id: int) -> None:
    """Background job: extract -> chunk -> embed -> index. Updates document status."""
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        try:
            pages = extract_text(Path(doc.stored_path), doc.file_type)
            chunks = chunk_pages(pages, document_id=doc.id, filename=doc.filename)
            if not chunks:
                raise ValueError("Document produced no usable text chunks.")

            get_vector_store().add_documents(chunks)

            doc.page_count = len(pages) if doc.file_type == "pdf" else None
            doc.chunk_count = len(chunks)
            doc.status = "ready"
            doc.error = None
        except Exception as exc:
            log.exception("Ingestion failed for document %s", document_id)
            doc.status = "failed"
            doc.error = _friendly_error(exc)
        db.commit()
    finally:
        db.close()


def _friendly_error(exc: Exception) -> str:
    msg = str(exc)
    if "connect" in msg.lower() or "refused" in msg.lower():
        return "Could not reach Ollama. Make sure it is running (ollama serve)."
    if "not found" in msg.lower() and "model" in msg.lower():
        return f"Embedding model missing. Run: ollama pull <model>. ({msg[:120]})"
    return msg[:300]
