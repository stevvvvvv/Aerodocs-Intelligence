"""Pipeline d'import : PDF -> pages nettoyées -> passages -> embeddings -> PostgreSQL."""
import hashlib
import logging
from datetime import date
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingestion.chunker import chunk_pages
from app.ingestion.pdf_extract import extract_pdf
from app.models import Chunk, Document, Page
from app.retrieval.embeddings import get_embedder

log = logging.getLogger(__name__)


class DuplicateDocumentError(ValueError):
    def __init__(self, existing: Document):
        super().__init__(f"Document déjà importé (id={existing.id}, {existing.title} {existing.version_label})")
        self.existing = existing


def refresh_current_version(session: Session, family: str) -> None:
    """Dans une famille, seule la version la plus récente (date d'effet, puis ordre d'import) est « en vigueur »."""
    docs = session.scalars(select(Document).where(Document.family == family)).all()
    if not docs:
        return
    latest = max(docs, key=lambda d: (d.effective_date or date.min, d.id))
    session.execute(update(Document).where(Document.family == family).values(is_current=False))
    session.execute(update(Document).where(Document.id == latest.id).values(is_current=True))


def ingest_pdf(
    session: Session,
    data: bytes,
    filename: str,
    family: str,
    version_label: str,
    effective_date: date | None = None,
    title: str | None = None,
) -> Document:
    settings = get_settings()
    digest = hashlib.sha256(data).hexdigest()
    existing = session.scalar(select(Document).where(Document.sha256 == digest))
    if existing:
        raise DuplicateDocumentError(existing)

    storage = Path(settings.upload_dir)
    storage.mkdir(parents=True, exist_ok=True)
    path = storage / f"{digest}.pdf"
    path.write_bytes(data)

    pages = extract_pdf(path)
    drafts = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
    title = title or Path(filename).stem

    # Le titre et la section sont ajoutés au texte encodé : un passage isolé
    # ("The interval is 500 FH") reste rattaché à son composant.
    embedder = get_embedder()
    vectors = embedder.embed_documents(
        [f"{title} | {d.section or ''}\n{d.text}" for d in drafts]
    )

    doc = Document(
        family=family.strip(),
        title=title,
        version_label=version_label.strip(),
        effective_date=effective_date,
        source_filename=filename,
        storage_path=str(path),
        sha256=digest,
        page_count=len(pages),
        chunk_count=len(drafts),
    )
    doc.pages = [Page(page_no=p.page_no, text=p.text) for p in pages]
    doc.chunks = [
        Chunk(
            ordinal=d.ordinal,
            section=d.section,
            page_start=d.page_start,
            page_end=d.page_end,
            text=d.text,
            embedding=v,
        )
        for d, v in zip(drafts, vectors)
    ]
    session.add(doc)
    session.flush()
    refresh_current_version(session, doc.family)
    session.commit()
    session.refresh(doc)
    log.info("Importé %s (%s) : %d pages, %d passages", title, version_label, len(pages), len(drafts))
    return doc
