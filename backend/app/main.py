import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import documents, query
from app.config import get_settings
from app.db import engine, init_db
from app.retrieval.embeddings import get_embedder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    get_embedder()  # charge le modèle au démarrage plutôt qu'à la première requête
    yield


app = FastAPI(
    title="AeroDocs Intelligence",
    description="Assistant RAG pour la documentation technique aéronautique : réponses sourcées, "
    "refus en cas de sources insuffisantes, détection de contradictions, gestion des versions.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
app.include_router(documents.router, prefix="/api")
app.include_router(query.router, prefix="/api")


@app.get("/api/health")
def health():
    s = get_settings()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "embeddings": get_embedder().name,
        "llm_provider": s.llm_provider,
        "llm_model": s.llm_model or None,
        "read_only": s.read_only,
    }


# Image tout-en-un (Hugging Face Space) : l'interface est servie par l'API, sur le même port.
# Monté en dernier pour que les routes /api restent prioritaires.
if get_settings().static_dir:
    app.mount("/", StaticFiles(directory=get_settings().static_dir, html=True), name="web")
