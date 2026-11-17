"""Mode sans LLM : la réponse est composée des phrases sources les plus pertinentes, citées.

Utile hors-ligne, en CI, et comme baseline : aucune hallucination possible, mais pas de
synthèse ni de reformulation."""
import math
import re

from app.generation.prompts import ABSTAIN_TOKEN
from app.retrieval.search import Hit

_TOKEN = re.compile(r"[a-zA-ZÀ-ÿ0-9]+(?:[.\-][a-zA-Z0-9]+)*")
_STOP = set(
    "a an the of to in on for and or is are be by with at as from that this these those it its what which "
    "when where how who shall should must may can do does any all each per i we you there their into than "
    "le la les de des du un une et ou en au aux pour par sur dans quel quelle quels quelles est sont "
    "quoi comment faut il elle doit doivent".split()
)
_SENT = re.compile(r"(?<=[.;!?])\s+|\n(?=[A-Z0-9(•\-])")


def _terms(text: str) -> list[str]:
    # troncature à 6 caractères : « inspections » et « inspected » se rejoignent (stemming grossier)
    return [t.lower()[:6] for t in _TOKEN.findall(text) if t.lower() not in _STOP and len(t) > 1]


def extractive_answer(question: str, hits: list[Hit], max_sentences: int = 3, min_coverage: float = 0.5) -> str:
    q_terms = set(_terms(question))
    if not q_terms:
        return ABSTAIN_TOKEN
    candidates: list[tuple[int, str, set[str]]] = []
    for i, h in enumerate(hits, 1):
        for s in _SENT.split(h.text):
            s = " ".join(s.split())
            if len(s.split()) >= 4:
                candidates.append((i, s, set(_terms(s))))
    if not candidates:
        return ABSTAIN_TOKEN

    df = {t: sum(t in c[2] for c in candidates) for t in q_terms}
    idf = {t: math.log(1 + len(candidates) / (1 + df[t])) for t in q_terms}
    total = sum(idf.values())

    scored = []
    for i, s, terms in candidates:
        matched = q_terms & terms
        # une phrase qui porte une valeur chiffrée répond plus probablement à « quel intervalle / quelle limite »
        bonus = 0.1 if re.search(r"\d", s) else 0.0
        scored.append((sum(idf[t] for t in matched) / total + bonus, i, s))
    scored.sort(key=lambda x: x[0], reverse=True)

    best_score = scored[0][0]
    if best_score < min_coverage:
        return ABSTAIN_TOKEN
    picked, seen = [], set()
    for score, i, s in scored:
        if score < best_score * 0.7 or len(picked) >= max_sentences:
            break
        if s in seen:
            continue
        seen.add(s)
        picked.append(f"{s.rstrip('.;')} [S{i}].")
    return "\n".join(picked)
