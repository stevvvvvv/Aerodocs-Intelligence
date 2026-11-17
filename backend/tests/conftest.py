"""Les tests tournent sur un vrai PostgreSQL + pgvector (pas de SQLite : on teste les vraies requêtes).

    docker compose up -d db   # ou une instance locale
    TEST_DATABASE_URL=postgresql+psycopg://aerodocs:aerodocs@localhost:5432/aerodocs_test pytest
"""
import os
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://aerodocs:aerodocs@localhost:5432/aerodocs_test"
)
os.environ["EMBEDDING_PROVIDER"] = "hashing"
os.environ["LLM_PROVIDER"] = "extractive"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="aerodocs-test-")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import engine  # noqa: E402
from scripts.make_demo_pdfs import DOCS, MANIFEST, build  # noqa: E402

DEMO_DIR = Path(tempfile.mkdtemp(prefix="aerodocs-demo-"))


@pytest.fixture(scope="session")
def demo_pdfs() -> dict[str, Path]:
    for fname, title, ref, content in DOCS:
        build(DEMO_DIR / fname, title, ref, content)
    return {f: DEMO_DIR / f for f, *_ in DOCS}


@pytest.fixture(scope="session")
def client():
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS query_logs, chunks, pages, documents CASCADE"))
    from app.main import app

    with TestClient(app) as c:
        yield c


def upload(client, path: Path, meta: dict):
    with open(path, "rb") as f:
        return client.post(
            "/api/documents",
            files={"file": (path.name, f, "application/pdf")},
            data={k: meta[k] for k in ("family", "version_label", "effective_date", "title")},
        )


@pytest.fixture(scope="session")
def seeded(client, demo_pdfs):
    docs = {}
    for m in MANIFEST:
        r = upload(client, demo_pdfs[m["file"]], m)
        assert r.status_code == 201, r.text
        docs[m["file"]] = r.json()
    return docs
