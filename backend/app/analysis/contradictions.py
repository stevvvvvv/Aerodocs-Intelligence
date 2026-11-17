"""Détection d'informations contradictoires entre les passages retrouvés.

Deux étages :
1. Heuristique (toujours active) : deux passages de documents différents donnent des valeurs
   différentes, dans la même unité, pour un contexte proche (« seal inspection ... 500 FH » vs
   « seal inspection ... 400 FH »).
2. Juge LLM (si un LLM est configuré) : confirme ou écarte chaque paire candidate. Le LLM est
   l'arbitre ; l'heuristique sert de filtre pour limiter le nombre d'appels.

Le résultat est un signal à vérifier par l'ingénieur, jamais une conclusion : le système
ne tranche pas quelle source a raison (applicabilité, MSN, effectivité... restent hors de portée).
"""
import json
import re
from dataclasses import dataclass
from itertools import combinations

import numpy as np

from app.generation.llm import LLM, LLMError
from app.generation.prompts import CONTRADICTION_SYSTEM
from app.retrieval.embeddings import get_embedder
from app.retrieval.search import Hit

_UNITS = {
    "fh": "FH", "flight hours": "FH", "flight hour": "FH",
    "hours": "h", "hour": "h", "hrs": "h", "hr": "h",
    "fc": "FC", "cycles": "FC", "cycle": "FC", "flight cycles": "FC", "landings": "FC",
    "months": "mo", "month": "mo", "mo": "mo",
    "days": "d", "day": "d", "years": "y", "year": "y",
    "psi": "psi", "bar": "bar", "nm": "N.m", "n.m": "N.m", "lbf.in": "lbf.in", "in-lb": "lbf.in",
    "mm": "mm", "in": "in", "°c": "°C", "%": "%", "kg": "kg", "lb": "lb",
}
_UNIT_RE = "|".join(sorted((re.escape(u) for u in _UNITS), key=len, reverse=True))
_QTY = re.compile(rf"(\d{{1,3}}(?:[ ,]\d{{3}})+|\d+(?:\.\d+)?)\s*({_UNIT_RE})(?![a-z])", re.I)
_WORD = re.compile(r"[a-z]{3,}")
_GENERIC = set("the and for with shall must should every each after before than within interval value".split())


@dataclass
class Quantity:
    value: float
    unit: str
    raw: str
    context: set[str]


@dataclass
class Contradiction:
    kind: str  # numeric | llm | version_change
    a: int  # index (0-based) dans hits
    b: int
    explanation: str
    confidence: str


def extract_quantities(text: str, window: int = 10) -> list[Quantity]:
    out = []
    low = text.lower()
    for m in _QTY.finditer(low):
        value = float(m.group(1).replace(",", "").replace(" ", ""))
        before = _WORD.findall(low[max(0, m.start() - 120): m.start()])[-window:]
        ctx = {w[:6] for w in before if w not in _GENERIC}
        start, end = max(0, m.start() - 60), min(len(text), m.end() + 20)
        start = text.rfind(" ", 0, start) + 1 if start else 0  # ne pas couper un mot
        end = text.find(" ", end) if text.find(" ", end) != -1 else len(text)
        out.append(Quantity(value, _UNITS[m.group(2).lower()], " ".join(text[start:end].split()), ctx))
    return out


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def numeric_conflict(a: Hit, b: Hit, min_overlap: float = 0.25) -> tuple[str, float] | None:
    best = None
    for qa in extract_quantities(a.text):
        for qb in extract_quantities(b.text):
            if qa.unit != qb.unit or qa.value == qb.value:
                continue
            overlap = _jaccard(qa.context, qb.context)
            if overlap >= min_overlap and (best is None or overlap > best[1]):
                best = (f"« …{qa.raw}… » / « …{qb.raw}… »", overlap)
    return best


def _parse_judge(raw: str) -> tuple[bool, str] | None:
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return bool(data.get("contradiction")), str(data.get("explanation", ""))
    except json.JSONDecodeError:
        return None


def detect_contradictions(
    hits: list[Hit], llm: LLM | None, pair_similarity: float, max_llm_pairs: int = 3
) -> list[Contradiction]:
    if len(hits) < 2:
        return []
    vecs = np.array(get_embedder().embed_documents([h.text for h in hits]))
    sims = vecs @ vecs.T

    candidates = []
    for i, j in combinations(range(len(hits)), 2):
        a, b = hits[i], hits[j]
        if a.document_id == b.document_id:
            continue
        num = numeric_conflict(a, b)
        same_topic = sims[i, j] >= pair_similarity or (a.section and a.section == b.section)
        if num or same_topic:
            candidates.append((i, j, num, float(sims[i, j])))

    results: list[Contradiction] = []
    llm_budget = max_llm_pairs
    for i, j, num, sim in sorted(candidates, key=lambda c: (c[2] is None, -c[3])):
        a, b = hits[i], hits[j]
        version_pair = a.family == b.family and a.version_label != b.version_label
        if version_pair:
            if num:  # même document, versions différentes : c'est une évolution, pas une contradiction
                old, new = (a, b) if not a.is_current else (b, a)
                results.append(Contradiction(
                    "version_change", i, j,
                    f"La valeur a changé entre la version {old.version_label} et la version "
                    f"{new.version_label} : {num[0]}", "high"))
            continue
        if not (a.is_current and b.is_current):
            continue  # une version remplacée ne « contredit » pas un autre document : elle n'est plus applicable

        if num is None:
            continue  # sans valeurs divergentes, un juge 7B produit surtout des faux positifs
        if llm is not None and llm_budget > 0:
            llm_budget -= 1
            try:
                verdict = _parse_judge(llm.generate(
                    CONTRADICTION_SYSTEM, f"EXCERPT A:\n{a.text}\n\nEXCERPT B:\n{b.text}", max_tokens=200))
            except LLMError:
                verdict = None
            if verdict is not None:
                if verdict[0]:
                    results.append(Contradiction(
                        "llm", i, j, f"Valeurs différentes, confirmées par le modèle : {num[0]}", "high"))
                continue  # le LLM a tranché : on n'ajoute pas l'heuristique en doublon
        if num:
            results.append(Contradiction(
                "numeric", i, j,
                f"Valeurs différentes pour un contexte proche : {num[0]}",
                "medium" if num[1] >= 0.4 else "low"))
    return results
