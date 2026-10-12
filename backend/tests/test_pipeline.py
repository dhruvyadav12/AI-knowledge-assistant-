"""End-to-end API test with no Ollama or Postgres required.

Swaps in SQLite, a bag-of-words embedder and a fake LLM so the real upload ->
chunk -> FAISS -> retrieve -> stream -> persist -> delete flow is exercised.
Run:  pytest -q
"""
import hashlib
import io
import json
import os
import re
import tempfile
from types import SimpleNamespace

import numpy as np
import pytest

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"
os.environ["INDEX_DIR"] = f"{_tmp}/index"

from fastapi.testclient import TestClient  # noqa: E402
from langchain_core.embeddings import Embeddings  # noqa: E402

from app.main import app  # noqa: E402
from app.services import rag, vector_store  # noqa: E402

DIM = 256


class BagOfWords(Embeddings):
    """Hash words into a fixed-size vector so similar text lands close together."""

    def _vec(self, text: str) -> list[float]:
        v = np.zeros(DIM, dtype="float32")
        for w in re.findall(r"[a-z0-9]+", text.lower()):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
        n = np.linalg.norm(v)
        return (v / n if n else v).tolist()

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


class FakeLLM:
    def invoke(self, prompt):
        return SimpleNamespace(content="standalone query")

    def stream(self, messages):
        for tok in ["The answer ", "is in ", "the context [1]."]:
            yield SimpleNamespace(content=tok)


@pytest.fixture(scope="module")
def client():
    vector_store._instance = vector_store.VectorStore(embeddings=BagOfWords())
    rag._llm = lambda: FakeLLM()
    with TestClient(app) as c:
        yield c


def make_pdf(pages: list[str]) -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    pdf = canvas.Canvas(buf)
    for text in pages:
        pdf.drawString(72, 750, text)
        pdf.showPage()
    pdf.save()
    return buf.getvalue()


def parse_sse(raw: str) -> list[tuple[str, dict]]:
    events = []
    for block in raw.strip().split("\n\n"):
        lines = dict(l.split(": ", 1) for l in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_full_flow(client):
    # no docs yet -> friendly reply, nothing crashes
    conv = client.post("/api/conversations").json()
    r = client.post(f"/api/conversations/{conv['id']}/messages/stream", json={"question": "hi"})
    assert "no indexed documents" in r.text

    # upload a 2-page PDF + a text file
    pdf = make_pdf([
        "Photosynthesis converts sunlight into chemical energy inside chloroplasts of plants.",
        "The Eiffel Tower in Paris was completed in 1889 and is made of wrought iron.",
    ])
    up = client.post("/api/documents", files=[
        ("files", ("science.pdf", pdf, "application/pdf")),
        ("files", ("notes.txt", b"Our refund policy allows returns within thirty days of purchase.", "text/plain")),
    ])
    assert up.status_code == 202
    docs = client.get("/api/documents").json()
    assert {d["status"] for d in docs} == {"ready"}, docs
    pdf_doc = next(d for d in docs if d["filename"] == "science.pdf")
    assert pdf_doc["page_count"] == 2 and pdf_doc["chunk_count"] >= 2

    # ask -> sources carry the right page, answer streams, message persisted
    conv = client.post("/api/conversations").json()
    r = client.post(
        f"/api/conversations/{conv['id']}/messages/stream",
        json={"question": "When was the Eiffel Tower completed?"},
    )
    events = parse_sse(r.text)
    kinds = [e[0] for e in events]
    assert kinds[0] == "sources" and kinds[-1] == "done" and "token" in kinds
    top = events[0][1]["sources"][0]
    assert top["filename"] == "science.pdf" and top["page"] == 2 and "1889" in top["snippet"]

    detail = client.get(f"/api/conversations/{conv['id']}").json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["sources"][0]["page"] == 2
    assert detail["title"].startswith("When was the Eiffel")

    # follow-up in same conversation works (exercises condense step)
    r = client.post(
        f"/api/conversations/{conv['id']}/messages/stream",
        json={"question": "and what is it made of?"},
    )
    assert parse_sse(r.text)[-1][0] == "done"

    # scoping to one document only returns that document
    txt_doc = next(d for d in docs if d["filename"] == "notes.txt")
    r = client.post(
        f"/api/conversations/{conv['id']}/messages/stream",
        json={"question": "tower", "document_ids": [txt_doc["id"]]},
    )
    assert {s["filename"] for s in parse_sse(r.text)[0][1]["sources"]} == {"notes.txt"}

    # original file is served for citation links
    assert client.get(f"/api/documents/{pdf_doc['id']}/file").status_code == 200

    # delete removes chunks from the index
    assert client.delete(f"/api/documents/{pdf_doc['id']}").status_code == 204
    r = client.post(
        f"/api/conversations/{conv['id']}/messages/stream", json={"question": "Eiffel Tower"}
    )
    assert all(s["filename"] != "science.pdf" for s in parse_sse(r.text)[0][1]["sources"])
    assert client.delete(f"/api/conversations/{conv['id']}").status_code == 204


def test_rejects_bad_uploads(client):
    r = client.post("/api/documents", files=[("files", ("x.exe", b"abc", "application/octet-stream"))])
    assert r.status_code == 415
    r = client.post("/api/documents", files=[("files", ("empty.txt", b"", "text/plain"))])
    assert r.status_code == 400


def test_index_persists_across_restart(client):
    n = vector_store.get_vector_store().size
    assert n > 0
    reloaded = vector_store.VectorStore(embeddings=BagOfWords())
    assert reloaded.size == n
