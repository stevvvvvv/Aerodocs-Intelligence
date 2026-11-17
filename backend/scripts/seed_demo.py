"""Importe le corpus de démonstration fictif dans la base (idempotent).

Usage : python -m scripts.seed_demo [dossier]   (depuis backend/)
"""
import sys
from datetime import date
from pathlib import Path

from app.db import SessionLocal, init_db
from app.ingestion.pipeline import DuplicateDocumentError, ingest_pdf
from scripts.make_demo_pdfs import DOCS, MANIFEST, build


def seed(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for fname, title, ref, content in DOCS:
        if not (folder / fname).exists():
            build(folder / fname, title, ref, content)
    init_db()
    with SessionLocal() as session:
        for m in MANIFEST:
            data = (folder / m["file"]).read_bytes()
            try:
                doc = ingest_pdf(session, data, m["file"], m["family"], m["version_label"],
                                 date.fromisoformat(m["effective_date"]), m["title"])
                print(f"importé  {doc.title} {doc.version_label} ({doc.chunk_count} passages)")
            except DuplicateDocumentError as e:
                session.rollback()
                print(f"déjà présent  {e.existing.title} {e.existing.version_label}")


if __name__ == "__main__":
    seed(Path(sys.argv[1] if len(sys.argv) > 1 else "../data/demo"))
