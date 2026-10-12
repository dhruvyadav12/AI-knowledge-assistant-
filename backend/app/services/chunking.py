from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..config import settings
from .extraction import PageText


def chunk_pages(
    pages: list[PageText], *, document_id: int, filename: str
) -> list[Document]:
    """Split page by page so each chunk keeps the page it came from."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[Document] = []
    for page in pages:
        for piece in splitter.split_text(page.text):
            piece = piece.strip()
            if len(piece) < 20:  # skip page numbers, stray headers, etc.
                continue
            chunks.append(
                Document(
                    page_content=piece,
                    metadata={
                        "document_id": document_id,
                        "filename": filename,
                        "page": page.page,
                        "chunk_index": len(chunks),
                    },
                )
            )
    return chunks
