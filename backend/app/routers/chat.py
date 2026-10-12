import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal, get_db
from ..models import Conversation, Document, Message, utcnow
from ..schemas import ChatRequest, ConversationDetail, ConversationOut
from ..services import rag

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conversations", tags=["chat"])


@router.get("", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db)):
    return db.scalars(select(Conversation).order_by(Conversation.updated_at.desc())).all()


@router.post("", response_model=ConversationOut, status_code=201)
def create_conversation(db: Session = Depends(get_db)):
    conv = Conversation()
    db.add(conv)
    db.commit()
    return conv


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    db.delete(conv)
    db.commit()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _title_from(question: str) -> str:
    title = " ".join(question.split())
    return title if len(title) <= 60 else title[:57] + "…"


@router.post("/{conversation_id}/messages/stream")
def ask(conversation_id: int, payload: ChatRequest, db: Session = Depends(get_db)):
    """Ask a question. Streams Server-Sent Events: sources -> token* -> done (or error)."""
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(404, "Conversation not found")

    question = payload.question.strip()
    history = [(m.role, m.content) for m in conv.messages]

    if not history:
        conv.title = _title_from(question)
    db.add(Message(conversation_id=conv.id, role="user", content=question))
    conv.updated_at = utcnow()
    db.commit()

    # Only search documents that finished indexing.
    ready_ids = set(db.scalars(select(Document.id).where(Document.status == "ready")))
    scope = [i for i in (payload.document_ids or []) if i in ready_ids] or None
    if payload.document_ids and scope is None:
        scope = [-1]  # selected docs aren't ready -> match nothing instead of everything
    has_ready_docs = bool(ready_ids)
    conv_id = conv.id

    def event_stream():
        answer_parts: list[str] = []
        sources: list[dict] = []
        try:
            if not has_ready_docs:
                answer_parts.append(
                    "There are no indexed documents yet. Upload a document and wait "
                    "for it to finish processing, then ask again."
                )
                yield _sse("sources", {"sources": []})
                yield _sse("token", {"text": answer_parts[0]})
            else:
                standalone = rag.condense_question(question, history)
                hits = rag.retrieve(standalone, scope)
                sources = rag.format_sources(hits)
                yield _sse("sources", {"sources": sources})
                for token in rag.stream_answer(question, hits, history):
                    answer_parts.append(token)
                    yield _sse("token", {"text": token})
        except Exception as exc:
            log.exception("Chat failed")
            msg = str(exc)
            if "connect" in msg.lower() or "refused" in msg.lower():
                msg = "Could not reach Ollama. Start it with `ollama serve` and try again."
            elif "not found" in msg.lower():
                msg = f"Model not found. Run `ollama pull {settings.llm_model}` and try again."
            yield _sse("error", {"detail": msg[:300]})
            if not answer_parts:
                return  # nothing worth saving

        answer = "".join(answer_parts).strip()
        if answer:
            with SessionLocal() as session:
                saved = Message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=answer,
                    sources=sources or None,
                )
                session.add(saved)
                c = session.get(Conversation, conv_id)
                if c is not None:
                    c.updated_at = utcnow()
                session.commit()
                yield _sse("done", {"message_id": saved.id})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
