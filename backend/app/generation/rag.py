"""Orchestration RAG : recherche -> garde-fou de pertinence -> génération -> vérification -> audit.

Le système a trois occasions de refuser, de la moins chère à la plus chère :
  1. avant le LLM, si aucun passage n'est assez proche de la question ;
  2. le LLM lui-même, s'il juge les sources insuffisantes (consigne explicite) ;
  3. après le LLM, si la réponse n'est pas suffisamment étayée par des citations valides.
"""
import logging
import time

from sqlalchemy.orm import Session

from app.analysis.contradictions import detect_contradictions
from app.config import get_settings
from app.generation.citations import check_citations
from app.generation.extractive import extractive_answer
from app.generation.llm import LLMError, get_llm
from app.generation.prompts import ABSTAIN_TOKEN, SYSTEM_PROMPT, build_prompt
from app.models import QueryLog
from app.retrieval.embeddings import get_embedder
from app.retrieval.search import Hit, SearchFilters, hybrid_search
from app.schemas import AnswerOut, ContradictionOut, QueryIn, SourceOut

log = logging.getLogger(__name__)

REFUSAL_MESSAGES = {
    "no_relevant_sources": "Aucun passage de la base documentaire ne traite suffisamment de cette question. "
    "Je préfère ne pas répondre plutôt que de risquer une information non sourcée.",
    "llm_abstained": "Les passages retrouvés ne contiennent pas l'information demandée. "
    "Vérifiez que le bon document (et la bonne version) est importé.",
    "unsupported_answer": "La réponse générée n'était pas suffisamment étayée par des citations vérifiables : "
    "elle a été bloquée.",
    "llm_error": "Le modèle de langage est indisponible. Les passages les plus pertinents sont listés ci-dessous.",
}


def _sources(hits: list[Hit], cited: set[int]) -> list[SourceOut]:
    return [
        SourceOut(
            ref=f"S{i}", chunk_id=h.chunk_id, document_id=h.document_id, title=h.title, family=h.family,
            version_label=h.version_label, is_current=h.is_current, section=h.section,
            page_start=h.page_start, page_end=h.page_end, excerpt=h.text, similarity=round(h.similarity, 4),
            cited=i in cited,
        )
        for i, h in enumerate(hits, 1)
    ]


def answer_question(session: Session, q: QueryIn) -> AnswerOut:
    s = get_settings()
    t0 = time.perf_counter()
    embedder = get_embedder()
    llm = get_llm()
    provider = llm.name if llm else "extractive"
    min_sim = s.min_similarity if s.min_similarity is not None else embedder.default_min_similarity
    pair_sim = (
        s.contradiction_pair_similarity
        if s.contradiction_pair_similarity is not None
        else embedder.default_pair_similarity
    )

    hits = hybrid_search(
        session, q.question,
        SearchFilters(q.include_superseded, q.family, q.document_ids),
        top_k=q.top_k,
    )
    top_sim = max((h.similarity for h in hits), default=None)
    warnings: list[str] = []

    def finish(status, answer=None, reason=None, cited=frozenset(), contradictions=(), coverage=None) -> AnswerOut:
        latency = int((time.perf_counter() - t0) * 1000)
        out = AnswerOut(
            status=status, answer=answer, refusal_reason=reason,
            refusal_message=REFUSAL_MESSAGES.get(reason) if reason else None,
            sources=_sources(hits, set(cited)),
            contradictions=[
                ContradictionOut(kind=c.kind, ref_a=f"S{c.a + 1}", ref_b=f"S{c.b + 1}",
                                 explanation=c.explanation, confidence=c.confidence)
                for c in contradictions
            ],
            warnings=warnings, citation_coverage=coverage,
            top_similarity=round(top_sim, 4) if top_sim is not None else None,
            llm_provider=provider, latency_ms=latency,
        )
        session.add(QueryLog(
            question=q.question, status=status, refusal_reason=reason, answer=answer,
            cited_chunk_ids=[hits[i - 1].chunk_id for i in cited], top_similarity=top_sim,
            llm_provider=provider, latency_ms=latency,
        ))
        session.commit()
        return out

    # 1. Garde-fou de pertinence, avant tout appel au LLM
    if not hits or top_sim is None or top_sim < min_sim:
        return finish("refused", reason="no_relevant_sources")

    if any(not h.is_current for h in hits):
        warnings.append("Certaines sources proviennent d'une version remplacée (SUPERSEDED) d'un document.")

    contradictions = detect_contradictions(hits, llm, pair_sim)

    # 2. Génération (ou extraction)
    try:
        raw = llm.generate(SYSTEM_PROMPT, build_prompt(q.question, hits)) if llm else extractive_answer(q.question, hits)
    except LLMError as e:
        log.error("LLM indisponible : %s", e)
        return finish("refused", reason="llm_error", contradictions=contradictions)

    # 3. Vérification des citations
    check = check_citations(raw.replace(ABSTAIN_TOKEN, "").strip(), len(hits))
    if ABSTAIN_TOKEN in raw and not check.cited:
        return finish("refused", reason="llm_abstained", contradictions=contradictions)
    if check.invalid:
        warnings.append(f"Citations inexistantes retirées de la réponse : {', '.join(f'S{i}' for i in check.invalid)}.")
    if not check.cited or check.coverage < s.min_citation_coverage:
        return finish("refused", reason="unsupported_answer", contradictions=contradictions,
                      coverage=round(check.coverage, 2))
    if check.coverage < 1:
        warnings.append("Une partie de la réponse n'est pas rattachée à une citation : à vérifier.")

    return finish("answered", answer=check.text, cited=check.cited, contradictions=contradictions,
                  coverage=round(check.coverage, 2))
