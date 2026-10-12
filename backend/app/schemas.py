from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_type: str
    size_bytes: int
    page_count: int | None
    chunk_count: int
    status: str
    error: str | None
    created_at: datetime


class SourceOut(BaseModel):
    index: int
    document_id: int
    filename: str
    page: int | None
    snippet: str
    score: float


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    sources: list[SourceOut] | None
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    # Restrict retrieval to these documents. Empty/None = search all ready documents.
    document_ids: list[int] | None = None
