"""Recherche hybride : similarité vectorielle (pgvector, HNSW) + plein texte PostgreSQL, fusion RRF.

Pourquoi hybride : la recherche sémantique comprend les reformulations, mais rate souvent
les identifiants exacts (« M.A.302 », « SB-32-014 », « P/N 201587 ») que le plein texte
retrouve parfaitement. La fusion par rangs (Reciprocal Rank Fusion) évite d'avoir à
calibrer ensemble deux scores qui ne sont pas comparables.
"""
from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.retrieval.embeddings import get_embedder

RRF_K = 60


@dataclass
class SearchFilters:
    include_superseded: bool = False
    family: str | None = None
    document_ids: list[int] | None = None


@dataclass
class Hit:
    chunk_id: int
    document_id: int
    title: str
    family: str
    version_label: str
    is_current: bool
    section: str | None
    page_start: int
    page_end: int
    text: str
    similarity: float  # cosinus question / passage
    lexical_rank: float
    score: float  # score RRF


def _where(filters: SearchFilters) -> tuple[str, dict]:
    clauses, params = [], {}
    if not filters.include_superseded and not filters.document_ids:
        clauses.append("d.is_current")
    if filters.family:
        clauses.append("d.family = :family")
        params["family"] = filters.family
    if filters.document_ids:
        clauses.append("d.id IN :doc_ids")
        params["doc_ids"] = list(filters.document_ids)
    return (" AND ".join(clauses) or "TRUE"), params


def _vec_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def hybrid_search(
    session: Session, query: str, filters: SearchFilters | None = None, top_k: int | None = None
) -> list[Hit]:
    s = get_settings()
    filters = filters or SearchFilters()
    top_k = top_k or s.top_k
    where, params = _where(filters)
    qvec = _vec_literal(get_embedder().embed_query(query))
    params |= {"qvec": qvec, "n": s.candidates, "q": query, "cfg": s.fts_config}

    def run(sql: str):
        stmt = text(sql)
        if "doc_ids" in params:
            stmt = stmt.bindparams(bindparam("doc_ids", expanding=True))
        return session.execute(stmt, params).all()

    vector_rows = run(
        f"""SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE {where}
            ORDER BY c.embedding <=> CAST(:qvec AS vector) LIMIT :n"""
    )
    # plainto_tsquery combine les termes en ET ; on passe en OU pour une question en langage naturel,
    # ts_rank_cd favorise ensuite les passages qui en contiennent le plus.
    lexical_rows = run(
        f"""WITH q AS (
              SELECT NULLIF(replace(plainto_tsquery(CAST(:cfg AS regconfig), :q)::text, '&', '|'), '')
                     AS tq)
            SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id, q
            WHERE {where} AND q.tq IS NOT NULL AND c.tsv @@ to_tsquery(CAST(:cfg AS regconfig), q.tq)
            ORDER BY ts_rank_cd(c.tsv, to_tsquery(CAST(:cfg AS regconfig), q.tq)) DESC LIMIT :n"""
    )

    scores: dict[int, float] = {}
    for rows in (vector_rows, lexical_rows):
        for rank, (cid,) in enumerate(rows):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
    if not scores:
        return []
    best = sorted(scores, key=scores.get, reverse=True)[:top_k]

    detail_sql = text(
        """WITH q AS (
             SELECT NULLIF(replace(plainto_tsquery(CAST(:cfg AS regconfig), :q)::text, '&', '|'), '') AS tq)
           SELECT c.id, d.id, d.title, d.family, d.version_label, d.is_current, c.section,
                  c.page_start, c.page_end, c.text,
                  1 - (c.embedding <=> CAST(:qvec AS vector)) AS sim,
                  CASE WHEN q.tq IS NULL THEN 0
                       ELSE ts_rank_cd(c.tsv, to_tsquery(CAST(:cfg AS regconfig), q.tq)) END AS lex
           FROM chunks c JOIN documents d ON d.id = c.document_id, q
           WHERE c.id IN :ids"""
    ).bindparams(bindparam("ids", expanding=True))
    rows = session.execute(detail_sql, {"ids": best, "qvec": qvec, "q": query, "cfg": s.fts_config}).all()
    hits = [
        Hit(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], float(r[10]), float(r[11]), scores[r[0]])
        for r in rows
    ]
    return sorted(hits, key=lambda h: h.score, reverse=True)
