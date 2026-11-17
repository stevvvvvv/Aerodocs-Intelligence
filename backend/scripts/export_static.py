"""Exporte un instantané de la démo pour un hébergement statique (GitHub Pages).

Les réponses sont calculées par le VRAI pipeline (recherche, garde-fous, génération,
vérification des citations) puis figées en JSON ; l'interface les rejoue sans serveur.

Usage (base peuplée par scripts/seed_demo.py) :
    python -m scripts.export_static /tmp/demo-export
    # depuis Docker : docker compose exec api python -m scripts.export_static /tmp/demo-export
    #                 docker compose cp api:/tmp/demo-export/. frontend/public/demo/
"""
import json
import shutil
import sys
from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path

from sqlalchemy import select

from app.analysis.versions import diff_versions
from app.config import get_settings
from app.db import SessionLocal
from app.generation.rag import answer_question
from app.models import Document
from app.retrieval.embeddings import get_embedder
from app.schemas import DocumentOut, QueryIn, SectionDiffOut, VersionDiffOut

QUESTIONS = [
    ("What is the inspection interval for the shock strut dynamic seals?", False),
    ("What is the inspection interval for the shock strut dynamic seals?", True),
    ("What is the torque value for the shock strut gland nut?", False),
    ("What nitrogen pressure should the main landing gear shock strut be charged to?", False),
    ("What is the maximum permissible pitting depth on the chrome surface?", False),
    ("How often is the lower bearing inspected for corrosion?", False),
    ("Which seal kit part number replaces the dynamic seals?", False),
    ("How often should hydraulic fluid samples be taken for contamination analysis?", False),
    ("Quel est l'intervalle d'inspection des joints dynamiques de l'amortisseur ?", False),
    ("What is the torque value for the wheel axle nut?", False),
    ("What is the nose wheel tire pressure?", False),
    ("What is the maximum takeoff weight of the aircraft?", False),
]


def main(out: Path) -> None:
    s = get_settings()
    out.mkdir(parents=True, exist_ok=True)
    (out / "pdfs").mkdir(exist_ok=True)
    with SessionLocal() as session:
        docs = session.scalars(select(Document).order_by(Document.family, Document.id)).all()
        for d in docs:
            shutil.copy(d.storage_path, out / "pdfs" / f"{d.id}.pdf")

        families: dict[str, list] = {}
        for d in docs:
            families.setdefault(d.family, []).append(DocumentOut.model_validate(d).model_dump(mode="json"))

        diffs = {}
        for fam_docs in families.values():
            for a, b in permutations(fam_docs, 2):
                unchanged, changes = diff_versions(session, a["id"], b["id"])
                diffs[f"{a['id']}-{b['id']}"] = VersionDiffOut(
                    family=a["family"], from_document=a, to_document=b, unchanged_sections=unchanged,
                    changes=[SectionDiffOut(**c.__dict__) for c in changes],
                ).model_dump(mode="json")

        answers = []
        for question, superseded in QUESTIONS:
            a = answer_question(session, QueryIn(question=question, include_superseded=superseded))
            answers.append({"question": question, "include_superseded": superseded, "answer": a.model_dump(mode="json")})
            print(f"{a.status:9} {a.latency_ms:6} ms  {question[:70]}")

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "health": {"embeddings": get_embedder().name, "llm_provider": s.llm_provider,
                   "llm_model": s.llm_model or None, "read_only": True},
        "documents": [doc for fam in families.values() for doc in fam],
        "families": [{"family": f, "versions": v} for f, v in families.items()],
        "diffs": diffs,
        "answers": answers,
    }
    (out / "snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {out}/snapshot.json ({len(answers)} réponses, {len(docs)} PDF)")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/demo-export"))
