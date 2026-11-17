"""Extraction du texte page par page + nettoyage des artefacts PDF (en-têtes, pieds de page, césures)."""
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass
class PageText:
    page_no: int  # numérotation physique, à partir de 1 (celle du lecteur PDF)
    text: str


class NoTextLayerError(ValueError):
    """PDF scanné (images) : pas de couche texte exploitable sans OCR."""


_DIGITS = re.compile(r"\d+")
_WS = re.compile(r"[ \t ]+")
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")


def _signature(line: str) -> str:
    # "Page 12 of 1265" et "Page 13 of 1265" doivent être reconnus comme la même ligne répétée
    return _DIGITS.sub("#", line.strip().lower())


def _strip_running_lines(pages: list[list[str]], edge: int = 3, ratio: float = 0.6) -> list[list[str]]:
    """Retire les lignes courtes répétées en haut/bas de page sur une majorité de pages (en-têtes, pieds).

    Seuil d'au moins 3 pages : sur un document court, une phrase de corps de texte répétée
    (« Record the task... ») ne doit pas être prise pour un pied de page."""
    if len(pages) < 3:
        return pages
    counts: Counter[str] = Counter()
    for lines in pages:
        edges = {_signature(l) for l in lines[:edge] + lines[-edge:] if l.strip() and len(l) <= 120}
        counts.update(edges)
    threshold = max(3, math.ceil(len(pages) * ratio))
    running = {sig for sig, n in counts.items() if n >= threshold}
    cleaned = []
    for lines in pages:
        n = len(lines)
        cleaned.append(
            [
                l
                for i, l in enumerate(lines)
                if not ((i < edge or i >= n - edge) and _signature(l) in running)
            ]
        )
    return cleaned


def clean_pages(raw_pages: list[str]) -> list[str]:
    split = []
    for raw in raw_pages:
        raw = _HYPHEN_BREAK.sub(r"\1\2", raw or "")
        lines = [_WS.sub(" ", l).strip() for l in raw.splitlines()]
        split.append([l for l in lines if l])
    split = _strip_running_lines(split)
    return ["\n".join(lines) for lines in split]


def extract_pdf(path: str | Path) -> list[PageText]:
    reader = PdfReader(str(path))
    raw = [page.extract_text() or "" for page in reader.pages]
    cleaned = clean_pages(raw)
    pages = [PageText(i + 1, t) for i, t in enumerate(cleaned)]
    total_chars = sum(len(p.text) for p in pages)
    if pages and total_chars < 20 * len(pages):
        raise NoTextLayerError(
            "Le PDF ne contient presque pas de texte extractible (document scanné ?). "
            "L'OCR n'est pas pris en charge dans cette version."
        )
    return pages
