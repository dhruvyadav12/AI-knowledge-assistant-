import re
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Document
from ..schemas import DocumentOut
from ..services.extraction import SUPPORTED_TYPES
from ..services.ingestion import ingest_document
from ..services.vector_store import get_vector_store

router = APIRouter(prefix="/api/documents", tags=["documents"])

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "txt": "text/plain; charset=utf-8",
    "md": "text/plain; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    return db.scalars(select(Document).order_by(Document.created_at.desc())).all()


@router.post("", response_model=list[DocumentOut], status_code=202)
async def upload_documents(
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Save files, then index them in the background. Poll GET /api/documents for status."""
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    limit = settings.max_upload_mb * 1024 * 1024
    created: list[Document] = []

    for upload in files:
        original = Path(upload.filename or "upload").name
        ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
        if ext not in SUPPORTED_TYPES:
            raise HTTPException(
                415, f"'{original}': unsupported type. Use {', '.join(sorted(SUPPORTED_TYPES))}."
            )

        content = await upload.read()
        if len(content) > limit:
            raise HTTPException(413, f"'{original}' exceeds {settings.max_upload_mb} MB.")
        if not content:
            raise HTTPException(400, f"'{original}' is empty.")

        safe = re.sub(r"[^A-Za-z0-9._-]", "_", original)
        stored = settings.upload_dir / f"{uuid.uuid4().hex}_{safe}"
        stored.write_bytes(content)

        doc = Document(
            filename=original,
            stored_path=str(stored),
            file_type=ext,
            size_bytes=len(content),
            status="processing",
        )
        db.add(doc)
        created.append(doc)

    db.commit()
    for doc in created:
        background.add_task(ingest_document, doc.id)
    return created


@router.get("/{document_id}/file")
def download_document(document_id: int, db: Session = Depends(get_db)):
    """Serve the original file so a citation can link to the exact page (#page=N)."""
    doc = db.get(Document, document_id)
    if doc is None or not Path(doc.stored_path).exists():
        raise HTTPException(404, "Document not found")
    return FileResponse(
        doc.stored_path,
        media_type=MEDIA_TYPES.get(doc.file_type, "application/octet-stream"),
        headers={"Content-Disposition": f'inline; filename="{doc.filename}"'},
    )


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    get_vector_store().delete_document(document_id)
    Path(doc.stored_path).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
