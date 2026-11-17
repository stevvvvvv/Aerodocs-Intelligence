"""Comparaison de deux versions d'un même document, section par section."""
import difflib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.chunker import split_sections
from app.ingestion.pdf_extract import PageText
from app.models import Page


@dataclass
class SectionChange:
    section: str
    change: str  # added | removed | modified
    page_from: int | None
    page_to: int | None
    diff: list[str]


def _pages(session: Session, document_id: int) -> list[PageText]:
    rows = session.scalars(select(Page).where(Page.document_id == document_id).order_by(Page.page_no)).all()
    return [PageText(p.page_no, p.text) for p in rows]


def _norm(text: str) -> list[str]:
    # comparaison phrase par phrase : la mise en page (retours à la ligne) change d'une révision à l'autre
    flat = " ".join(text.split())
    return [s.strip() for s in flat.replace("; ", ";\n").replace(". ", ".\n").splitlines() if s.strip()]


def diff_versions(session: Session, from_id: int, to_id: int, max_lines: int = 40) -> tuple[int, list[SectionChange]]:
    old = {s.title: s for s in split_sections(_pages(session, from_id))}
    new = {s.title: s for s in split_sections(_pages(session, to_id))}
    changes: list[SectionChange] = []
    unchanged = 0

    for title, sec in new.items():
        if title not in old:
            changes.append(SectionChange(title, "added", None, sec.first_page, [f"+ {l}" for l in _norm(sec.text)][:max_lines]))
            continue
        a, b = _norm(old[title].text), _norm(sec.text)
        if a == b:
            unchanged += 1
            continue
        lines = [
            l for l in difflib.unified_diff(a, b, lineterm="", n=0)
            if l[:1] in "+-" and not l.startswith(("+++", "---"))
        ]
        changes.append(SectionChange(title, "modified", old[title].first_page, sec.first_page, [f"{l[0]} {l[1:]}" for l in lines][:max_lines]))
    for title, sec in old.items():
        if title not in new:
            changes.append(SectionChange(title, "removed", sec.first_page, None, [f"- {l}" for l in _norm(sec.text)][:max_lines]))
    changes.sort(key=lambda c: (c.page_to or c.page_from or 0))
    return unchanged, changes
