"""Retrieval-augmented generation: condense -> retrieve -> prompt -> stream."""
from collections.abc import Iterator

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from ..config import settings
from .vector_store import get_vector_store

SYSTEM_PROMPT = """You are a careful knowledge assistant. Answer the user's question \
using ONLY the numbered context excerpts provided.

Rules:
- Cite the excerpts you rely on with bracketed numbers such as [1] or [2][3], placed right after the claim.
- If the excerpts do not contain the answer, say you couldn't find it in the uploaded documents. Do not guess or use outside knowledge.
- Be concise and direct. Use short paragraphs or bullet points when it helps.
- Never invent citations; only use numbers that appear in the context."""

CONDENSE_PROMPT = """Rewrite the user's latest message as a single standalone search query, \
using the chat history to resolve pronouns and references. Do not answer it. \
Output only the rewritten query.

Chat history:
{history}

Latest message: {question}

Standalone query:"""

NO_CONTEXT_REPLY = (
    "I couldn't find anything relevant in the uploaded documents. "
    "Try rephrasing the question, or upload a document that covers this topic."
)


def _llm() -> ChatOllama:
    return ChatOllama(
        model=settings.llm_model,
        base_url=settings.ollama_base_url,
        temperature=settings.llm_temperature,
    )


def condense_question(question: str, history: list[tuple[str, str]]) -> str:
    """Turn a follow-up like 'what about its cost?' into a self-contained query."""
    if not history:
        return question
    transcript = "\n".join(
        f"{role.capitalize()}: {content[:600]}" for role, content in history[-4:]
    )
    try:
        out = _llm().invoke(
            CONDENSE_PROMPT.format(history=transcript, question=question)
        )
        rewritten = str(out.content).strip().strip('"')
        return rewritten or question
    except Exception:
        return question  # retrieval still works with the raw question


def retrieve(
    query: str, document_ids: list[int] | None = None
) -> list[tuple[Document, float]]:
    return get_vector_store().search(query, settings.top_k, document_ids)


def format_sources(hits: list[tuple[Document, float]]) -> list[dict]:
    sources = []
    for i, (doc, distance) in enumerate(hits, start=1):
        text = " ".join(doc.page_content.split())
        sources.append(
            {
                "index": i,
                "document_id": int(doc.metadata["document_id"]),
                "filename": doc.metadata.get("filename", "unknown"),
                "page": doc.metadata.get("page"),
                "snippet": text[:400] + ("…" if len(text) > 400 else ""),
                "score": round(1 / (1 + float(distance)), 3),
            }
        )
    return sources


def _build_context(hits: list[tuple[Document, float]]) -> str:
    blocks = []
    for i, (doc, _) in enumerate(hits, start=1):
        page = doc.metadata.get("page")
        where = f"{doc.metadata.get('filename')}" + (f", page {page}" if page else "")
        blocks.append(f"[{i}] ({where})\n{doc.page_content}")
    return "\n\n".join(blocks)


def stream_answer(
    question: str,
    hits: list[tuple[Document, float]],
    history: list[tuple[str, str]],
) -> Iterator[str]:
    if not hits:
        yield NO_CONTEXT_REPLY
        return

    messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
    for role, content in history[-settings.history_messages :]:
        messages.append(
            HumanMessage(content=content) if role == "user" else AIMessage(content=content)
        )
    messages.append(
        HumanMessage(
            content=f"Context excerpts:\n\n{_build_context(hits)}\n\nQuestion: {question}"
        )
    )

    for chunk in _llm().stream(messages):
        if chunk.content:
            yield str(chunk.content)
