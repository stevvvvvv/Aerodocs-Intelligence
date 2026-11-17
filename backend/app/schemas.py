from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family: str
    title: str
    version_label: str
    effective_date: date | None
    is_current: bool
    source_filename: str
    page_count: int
    chunk_count: int
    uploaded_at: datetime


class QueryIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    include_superseded: bool = False
    family: str | None = None
    document_ids: list[int] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


class SourceOut(BaseModel):
    ref: str  # "S1"
    chunk_id: int
    document_id: int
    title: str
    family: str
    version_label: str
    is_current: bool
    section: str | None
    page_start: int
    page_end: int
    excerpt: str
    similarity: float
    cited: bool


class ContradictionOut(BaseModel):
    kind: Literal["numeric", "llm", "version_change"]
    ref_a: str
    ref_b: str
    explanation: str
    confidence: Literal["low", "medium", "high"]


RefusalReason = Literal["no_relevant_sources", "llm_abstained", "unsupported_answer", "llm_error"]


class AnswerOut(BaseModel):
    status: Literal["answered", "refused"]
    answer: str | None
    refusal_reason: RefusalReason | None = None
    refusal_message: str | None = None
    sources: list[SourceOut]
    contradictions: list[ContradictionOut]
    warnings: list[str]
    citation_coverage: float | None = None
    top_similarity: float | None = None
    llm_provider: str
    latency_ms: int


class SectionDiffOut(BaseModel):
    section: str
    change: Literal["added", "removed", "modified"]
    page_from: int | None
    page_to: int | None
    diff: list[str]


class VersionDiffOut(BaseModel):
    family: str
    from_document: DocumentOut
    to_document: DocumentOut
    unchanged_sections: int
    changes: list[SectionDiffOut]
