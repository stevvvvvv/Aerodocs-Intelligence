"""Découpage en passages (chunks) qui conservent la section et les pages d'origine.

Le découpage respecte la structure des documents aéronautiques : un nouveau titre de
section (M.A.301, CS 25.571, AMC1 145.A.30, 2.3 Servicing, SUBPART C...) force un nouveau
passage, pour qu'une citation pointe toujours vers une section cohérente.
"""
import re
from dataclasses import dataclass, field

from app.ingestion.pdf_extract import PageText

_HEADING_PATTERNS = [
    # Références réglementaires EASA : M.A.301, 145.A.30, CAMO.A.315, ML.A.302, 66.B.20
    re.compile(r"^(AMC\d*|GM\d*)?\s*(M|ML|CAMO|CAO|145|66|147|T|21)\.[AB]\.\d+[A-Z]?\b"),
    # Spécifications de certification : CS 25.571, CS-E 515, AMC 25.1309
    re.compile(r"^(AMC|GM)?\s*CS[ -]?[A-Z0-9]*\s?\d+(\.\d+)*\b"),
    re.compile(r"^AMC\s?\d+(\.\d+)+\b"),
    # Structure de manuels : SUBPART C, SECTION 2, CHAPTER 32, APPENDIX I, TASK 32-11-00-200-801
    re.compile(r"^(SUBPART|SECTION|CHAPTER|APPENDIX|ANNEX|PART|TASK)\s+[A-Z0-9][\w\-.]*", re.I),
    # Numérotation décimale suivie d'un titre : "2.3 Servicing of the shock strut"
    re.compile(r"^\d{1,2}(\.\d{1,2}){0,3}\.?\s+[A-Z][A-Za-z]"),
]


def is_heading(line: str) -> bool:
    line = line.strip()
    if not (3 <= len(line) <= 140) or line.endswith((",", ";")):
        return False
    if any(p.match(line) for p in _HEADING_PATTERNS):
        # une phrase longue qui commence par "1. The operator shall..." n'est pas un titre
        return len(line.split()) <= 16 and not line.endswith(".")
    # titres en capitales ("SERVICING", "TORQUE VALUES"), mais pas une référence isolée ("MIL-PRF-5606.")
    letters = [c for c in line if c.isalpha()]
    non_space = [c for c in line if not c.isspace()]
    return (
        len(letters) >= 4
        and len(line) <= 90
        and not line.endswith(".")
        and sum(c.isupper() for c in letters) / len(letters) > 0.85
        and len(letters) / len(non_space) >= 0.7
    )


@dataclass
class ChunkDraft:
    ordinal: int
    section: str | None
    page_start: int
    page_end: int
    text: str


@dataclass
class _Line:
    page: int
    section: str | None
    text: str


@dataclass
class _Buffer:
    lines: list[_Line] = field(default_factory=list)

    @property
    def size(self) -> int:
        return sum(len(l.text) + 1 for l in self.lines)


def _iter_lines(pages: list[PageText]):
    section = None
    for page in pages:
        for raw in page.text.splitlines():
            if is_heading(raw):
                section = raw.strip()[:280]
            yield _Line(page.page_no, section, raw.strip())


def chunk_pages(pages: list[PageText], chunk_size: int = 1000, overlap: int = 150) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    buf = _Buffer()

    def flush(keep_overlap: bool) -> None:
        nonlocal buf
        content = [l for l in buf.lines if l.text]
        if content and any(not is_heading(l.text) for l in content):
            chunks.append(
                ChunkDraft(
                    ordinal=len(chunks),
                    section=content[-1].section,
                    page_start=min(l.page for l in content),
                    page_end=max(l.page for l in content),
                    text="\n".join(l.text for l in content),
                )
            )
        tail: list[_Line] = []
        if keep_overlap:
            size = 0
            for l in reversed(buf.lines):
                if size + len(l.text) > overlap:
                    break
                tail.insert(0, l)
                size += len(l.text) + 1
        buf = _Buffer(tail)

    current_section = object()
    for line in _iter_lines(pages):
        if line.section != current_section:
            flush(keep_overlap=False)  # pas de chevauchement entre deux sections
            current_section = line.section
        buf.lines.append(line)
        if buf.size >= chunk_size:
            flush(keep_overlap=True)
    flush(keep_overlap=False)
    return chunks


@dataclass
class Section:
    title: str
    first_page: int
    text: str


def split_sections(pages: list[PageText]) -> list[Section]:
    """Découpe un document en sections (pour comparer deux versions)."""
    sections: list[Section] = []
    for line in _iter_lines(pages):
        title = line.section or "(début du document)"
        if not sections or sections[-1].title != title:
            sections.append(Section(title, line.page, ""))
        if line.text != title:
            sections[-1].text += line.text + "\n"
    return sections
