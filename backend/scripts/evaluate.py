"""Évaluation du pipeline sur un jeu de questions annotées (eval/questions.jsonl).

Mesure séparément chaque maillon, pour savoir QUOI améliorer :
- Récupération  : hit@k et MRR (le bon passage est-il retrouvé, à quel rang ?)
- Réponse       : exactitude (la valeur attendue figure dans la réponse) et citation correcte
- Refus         : précision / rappel du refus sur les questions sans réponse dans le corpus
- Contradictions: détectée quand attendue

Usage (depuis backend/, base peuplée par scripts/seed_demo.py) :
    python -m scripts.evaluate [--out ../docs/eval_results.md]
"""
import argparse
import json
import statistics
from pathlib import Path

from app.config import get_settings
from app.db import SessionLocal
from app.generation.rag import answer_question
from app.retrieval.embeddings import get_embedder
from app.retrieval.search import SearchFilters, hybrid_search
from app.schemas import QueryIn


def _match(hit_family: str, hit_section: str | None, q: dict) -> bool:
    return hit_family == q["expected_family"] and q["expected_section"].lower() in (hit_section or "").lower()


def run(path: Path) -> dict:
    questions = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    rows = []
    with SessionLocal() as session:
        for q in questions:
            hits = hybrid_search(session, q["question"], SearchFilters())
            out = answer_question(session, QueryIn(question=q["question"]))
            row = {"id": q["id"], "question": q["question"], "answerable": q["answerable"],
                   "lang": q.get("lang", "en"), "status": out.status, "reason": out.refusal_reason,
                   "top_similarity": out.top_similarity, "latency_ms": out.latency_ms}
            if q["answerable"]:
                rank = next((i for i, h in enumerate(hits, 1) if _match(h.family, h.section, q)), None)
                answer = out.answer or ""
                cited = [s for s in out.sources if s.cited]
                row |= {
                    "rank": rank,
                    "correct": out.status == "answered" and all(v in answer for v in q["expected_values"]),
                    "citation_ok": any(_match(s.family, s.section, q) for s in cited),
                }
                if q.get("expect_contradiction"):
                    row["contradiction_found"] = any(c.kind in ("numeric", "llm") for c in out.contradictions)
            rows.append(row)

    ans = [r for r in rows if r["answerable"]]
    unans = [r for r in rows if not r["answerable"]]
    refused = [r for r in rows if r["status"] == "refused"]
    k = get_settings().top_k
    metrics = {
        f"retrieval_hit@{k}": sum(r["rank"] is not None for r in ans) / len(ans),
        "retrieval_mrr": statistics.mean(1 / r["rank"] if r["rank"] else 0 for r in ans),
        "answer_accuracy": sum(r["correct"] for r in ans) / len(ans),
        "citation_accuracy": sum(r["citation_ok"] for r in ans if r["status"] == "answered")
        / max(1, sum(r["status"] == "answered" for r in ans)),
        "refusal_recall": sum(r["status"] == "refused" for r in unans) / len(unans),
        "refusal_precision": sum(not r["answerable"] for r in refused) / max(1, len(refused)),
        "false_refusals": sum(r["status"] == "refused" for r in ans),
        "contradiction_recall": statistics.mean(
            r["contradiction_found"] for r in ans if "contradiction_found" in r) if any(
            "contradiction_found" in r for r in ans) else None,
        "latency_p50_ms": statistics.median(r["latency_ms"] for r in rows),
    }
    return {"metrics": metrics, "rows": rows, "n_answerable": len(ans), "n_unanswerable": len(unans)}


def to_markdown(res: dict) -> str:
    s = get_settings()
    lines = [
        "# Résultats d'évaluation",
        "",
        f"Configuration : embeddings `{get_embedder().name}`, génération `{s.llm_provider}`"
        f"{' / ' + s.llm_model if s.llm_model else ''}, top_k={s.top_k}.",
        f"Jeu : {res['n_answerable']} questions avec réponse, {res['n_unanswerable']} sans réponse (corpus démo fictif).",
        "",
        "| Métrique | Valeur |",
        "|---|---|",
    ]
    for k, v in res["metrics"].items():
        lines.append(f"| {k} | {v:.2f} |" if isinstance(v, float) else f"| {k} | {v} |")
    lines += ["", "| id | langue | attendu | statut | rang | correct | citation | sim. max |", "|---|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        lines.append(
            f"| {r['id']} | {r['lang']} | {'réponse' if r['answerable'] else 'refus'} | "
            f"{r['status']}{' (' + r['reason'] + ')' if r['reason'] else ''} | {r.get('rank', '')} | "
            f"{r.get('correct', '')} | {r.get('citation_ok', '')} | {r['top_similarity']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="eval/questions.jsonl")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    res = run(Path(args.questions))
    md = to_markdown(res)
    print(md)
    if args.out:
        Path(args.out).write_text(md)
