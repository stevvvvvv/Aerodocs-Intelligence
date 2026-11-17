from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.versions import diff_versions
from app.config import get_settings
from app.db import get_session
from app.ingestion.pdf_extract import NoTextLayerError
from app.ingestion.pipeline import DuplicateDocumentError, ingest_pdf, refresh_current_version
from app.models import Document, Page
from app.schemas import DocumentOut, SectionDiffOut, VersionDiffOut

router = APIRouter(tags=["documents"])


def _writable() -> None:
    if get_settings().read_only:
        raise HTTPException(403, "Démo en lecture seule : l'import et la suppression sont désactivés. "
                                 "Lancez le projet en local (docker compose) pour importer vos PDF.")
MAX_UPLOAD_MB = 200


@router.post("/documents", response_model=DocumentOut, status_code=201)
def upload_document(  # sync : FastAPI l'exécute dans un thread, l'ingestion ne bloque pas la boucle
    file: UploadFile = File(...),
    family: str = Form(..., description="Identifiant commun à toutes les versions, ex. 'EAR Continuing Airworthiness'"),
    version_label: str = Form(..., description="ex. 'Rev. July 2024'"),
    effective_date: date | None = Form(None),
    title: str | None = Form(None),
    session: Session = Depends(get_session),
):
    _writable()
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(415, "Seuls les fichiers PDF sont acceptés.")
    data = file.file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"Fichier trop volumineux (> {MAX_UPLOAD_MB} Mo).")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "Le fichier n'est pas un PDF valide.")
    try:
        return ingest_pdf(session, data, file.filename, family, version_label, effective_date, title)
    except DuplicateDocumentError as e:
        raise HTTPException(409, str(e)) from e
    except NoTextLayerError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(session: Session = Depends(get_session)):
    return session.scalars(
        select(Document).order_by(Document.family, Document.effective_date.desc().nulls_last(), Document.id.desc())
    ).all()


def _get(session: Session, document_id: int) -> Document:
    doc = session.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document introuvable.")
    return doc


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, session: Session = Depends(get_session)):
    return _get(session, document_id)


@router.get("/documents/{document_id}/file")
def get_document_file(document_id: int, session: Session = Depends(get_session)):
    doc = _get(session, document_id)
    return FileResponse(doc.storage_path, media_type="application/pdf", filename=doc.source_filename,
                        content_disposition_type="inline")


@router.get("/documents/{document_id}/pages/{page_no}")
def get_page(document_id: int, page_no: int, session: Session = Depends(get_session)):
    page = session.scalar(select(Page).where(Page.document_id == document_id, Page.page_no == page_no))
    if not page:
        raise HTTPException(404, "Page introuvable.")
    return {"document_id": document_id, "page_no": page_no, "text": page.text}


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: int, session: Session = Depends(get_session)):
    _writable()
    doc = _get(session, document_id)
    family = doc.family
    session.delete(doc)
    session.flush()
    refresh_current_version(session, family)
    session.commit()


@router.get("/families")
def list_families(session: Session = Depends(get_session)):
    docs = session.scalars(select(Document).order_by(Document.family, Document.id)).all()
    families: dict[str, list[DocumentOut]] = {}
    for d in docs:
        families.setdefault(d.family, []).append(DocumentOut.model_validate(d))
    return [{"family": f, "versions": v} for f, v in families.items()]


@router.get("/versions/diff", response_model=VersionDiffOut)
def version_diff(from_id: int, to_id: int, session: Session = Depends(get_session)):
    a, b = _get(session, from_id), _get(session, to_id)
    if a.family != b.family:
        raise HTTPException(400, "Les deux documents doivent appartenir à la même famille.")
    unchanged, changes = diff_versions(session, a.id, b.id)
    return VersionDiffOut(
        family=a.family,
        from_document=DocumentOut.model_validate(a),
        to_document=DocumentOut.model_validate(b),
        unchanged_sections=unchanged,
        changes=[SectionDiffOut(**c.__dict__) for c in changes],
    )
