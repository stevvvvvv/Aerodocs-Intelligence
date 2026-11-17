from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    """Crée l'extension pgvector et les tables ; vérifie la cohérence de dimension des embeddings."""
    from app.models import Base

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        dim = conn.execute(
            text(
                "SELECT atttypmod FROM pg_attribute "
                "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
            )
        ).scalar()
    if dim is not None and dim != settings.embedding_dim:
        raise RuntimeError(
            f"La colonne embedding est en dimension {dim} mais EMBEDDING_DIM={settings.embedding_dim}. "
            "Changer de modèle d'embeddings impose de réindexer (supprimer le volume ou les tables)."
        )


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
