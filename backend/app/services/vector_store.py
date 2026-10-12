"""FAISS-backed semantic index, persisted to disk and shared by the whole app.

One index holds chunks from every document. Each chunk carries `document_id`
metadata so we can (a) scope a search to selected documents and (b) delete a
document's chunks later.
"""
import threading
import uuid

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

from ..config import settings

INDEX_NAME = "index"


class VectorStore:
    def __init__(self, embeddings=None):
        self._lock = threading.RLock()
        self._embeddings = embeddings or OllamaEmbeddings(
            model=settings.embedding_model, base_url=settings.ollama_base_url
        )
        self._store: FAISS | None = None
        settings.index_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    # ---- persistence -------------------------------------------------
    def _load(self) -> None:
        if (settings.index_dir / f"{INDEX_NAME}.faiss").exists():
            self._store = FAISS.load_local(
                str(settings.index_dir),
                self._embeddings,
                index_name=INDEX_NAME,
                allow_dangerous_deserialization=True,  # we only load our own index
            )

    def _save(self) -> None:
        if self._store is not None:
            self._store.save_local(str(settings.index_dir), index_name=INDEX_NAME)

    # ---- writes ------------------------------------------------------
    def add_documents(self, docs: list[Document], batch_size: int = 32) -> None:
        if not docs:
            return
        # Embed outside the lock (slow); only touch the index while holding it.
        texts = [d.page_content for d in docs]
        vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            vectors.extend(self._embeddings.embed_documents(texts[i : i + batch_size]))

        ids = [uuid.uuid4().hex for _ in docs]
        pairs = list(zip(texts, vectors))
        metadatas = [d.metadata for d in docs]
        with self._lock:
            if self._store is None:
                self._store = FAISS.from_embeddings(
                    pairs, self._embeddings, metadatas=metadatas, ids=ids
                )
            else:
                self._store.add_embeddings(pairs, metadatas=metadatas, ids=ids)
            self._save()

    def delete_document(self, document_id: int) -> None:
        with self._lock:
            if self._store is None:
                return
            ids = [
                chunk_id
                for chunk_id, doc in self._store.docstore._dict.items()
                if doc.metadata.get("document_id") == document_id
            ]
            if ids:
                self._store.delete(ids)
                self._save()

    # ---- reads -------------------------------------------------------
    def search(
        self, query: str, k: int, document_ids: list[int] | None = None
    ) -> list[tuple[Document, float]]:
        """Return (chunk, distance) pairs; lower distance means more similar."""
        with self._lock:
            store = self._store
        if store is None:
            return []

        allowed = set(document_ids) if document_ids else None
        results = store.similarity_search_with_score(
            query,
            k=k,
            filter=(lambda m: m.get("document_id") in allowed) if allowed else None,
            fetch_k=max(k * 20, 100) if allowed else k,
        )
        return results

    @property
    def size(self) -> int:
        with self._lock:
            return self._store.index.ntotal if self._store else 0


_instance: VectorStore | None = None
_instance_lock = threading.Lock()


def get_vector_store() -> VectorStore:
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = VectorStore()
        return _instance
