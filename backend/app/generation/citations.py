"""Vérification des citations après génération : on ne fait pas confiance au LLM sur parole."""
import re
from dataclasses import dataclass

_CITATION_GROUP = re.compile(r"\[(\s*S\d+(?:\s*[,;]\s*S?\d+)*\s*)\]")
_REF = re.compile(r"S?(\d+)")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý0-9\"'(])|\n+")


@dataclass
class CitationCheck:
    text: str  # réponse nettoyée (citations invalides retirées, format normalisé)
    cited: list[int]  # numéros de sources valides citées, dans l'ordre d'apparition
    invalid: list[int]  # numéros cités qui n'existent pas dans le contexte
    coverage: float  # part des phrases portant au moins une citation valide


_ABBREV = {"rev.", "no.", "fig.", "para.", "e.g.", "i.e.", "ref.", "vol.", "chap.", "approx.", "max.", "min.", "p.", "pp.", "art."}


def _split_sentences(text: str) -> list[str]:
    parts: list[str] = []
    for p in (p.strip() for p in _SENTENCE_SPLIT.split(text) if p and p.strip()):
        last = parts[-1].split()[-1].lower() if parts else ""
        if parts and (last in _ABBREV or re.fullmatch(r"[a-z]\.", last)):
            parts[-1] += " " + p  # « Rev. B » ou « No. 1321/2014 » ne terminent pas une phrase
        else:
            parts.append(p)
    # les lignes d'introduction de liste ("Conditions :") ne sont pas des affirmations
    return [p for p in parts if len(p.split()) >= 3 and not p.endswith(":")]


def check_citations(answer: str, n_sources: int) -> CitationCheck:
    cited: list[int] = []
    invalid: list[int] = []

    def normalize(m: re.Match) -> str:
        refs = [int(x) for x in _REF.findall(m.group(1))]
        ok = [r for r in refs if 1 <= r <= n_sources]
        invalid.extend(r for r in refs if not 1 <= r <= n_sources)
        for r in ok:
            if r not in cited:
                cited.append(r)
        return "".join(f"[S{r}]" for r in ok)

    cleaned = _CITATION_GROUP.sub(normalize, answer)
    cleaned = re.sub(r"\s*\[\s*\]", "", cleaned).strip()
    sentences = _split_sentences(cleaned)
    with_cite = [s for s in sentences if re.search(r"\[S\d+\]", s)]
    coverage = len(with_cite) / len(sentences) if sentences else 0.0
    return CitationCheck(cleaned, cited, invalid, coverage)
