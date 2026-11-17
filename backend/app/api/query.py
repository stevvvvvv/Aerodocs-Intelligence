from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.generation.rag import answer_question
from app.models import QueryLog
from app.retrieval.search import SearchFilters, hybrid_search
from app.schemas import AnswerOut, QueryIn

router = APIRouter(tags=["query"])


@router.post("/query", response_model=AnswerOut)
def query(q: QueryIn, session: Session = Depends(get_session)):
    return answer_question(session, q)


@router.post("/search")
def search(q: QueryIn, session: Session = Depends(get_session)):
    """Recherche seule (sans génération) : utile pour déboguer la récupération."""
    hits = hybrid_search(session, q.question, SearchFilters(q.include_superseded, q.family, q.document_ids), q.top_k)
    return [h.__dict__ for h in hits]


@router.get("/queries")
def query_log(limit: int = 50, session: Session = Depends(get_session)):
    rows = session.scalars(select(QueryLog).order_by(QueryLog.id.desc()).limit(min(limit, 500))).all()
    return [
        {"id": r.id, "question": r.question, "status": r.status, "refusal_reason": r.refusal_reason,
         "top_similarity": r.top_similarity, "llm_provider": r.llm_provider, "latency_ms": r.latency_ms,
         "cited_chunk_ids": r.cited_chunk_ids, "created_at": r.created_at}
        for r in rows
    ]
