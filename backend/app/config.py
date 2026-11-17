"""Configuration centralisée (variables d'environnement, fichier .env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    database_url: str = "postgresql+psycopg://aerodocs:aerodocs@localhost:5432/aerodocs"
    upload_dir: str = "./storage"
    # Démo publique (Hugging Face Space) : import et suppression désactivés
    read_only: bool = False
    # Si renseigné, l'API sert aussi l'interface compilée (image tout-en-un)
    static_dir: str = ""

    # --- Embeddings -------------------------------------------------------
    # "local"   : sentence-transformers (multilingual-e5-small par défaut, 384 dim)
    # "hashing" : embeddings lexicaux déterministes, sans téléchargement (tests / hors-ligne)
    embedding_provider: str = "local"
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dim: int = 384

    # --- LLM ----------------------------------------------------------------
    # "anthropic" | "openai" | "ollama" | "extractive" (aucun LLM, phrases sources citées)
    llm_provider: str = "extractive"
    llm_model: str = ""
    llm_temperature: float = 0.0
    llm_timeout_s: float = 60.0
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    ollama_url: str = "http://ollama:11434"
    # Ollama tronque silencieusement le prompt au-delà de num_ctx (2048 par défaut sur certaines versions) :
    # les sources seraient coupées et le modèle répondrait « sources insuffisantes ».
    ollama_num_ctx: int = 8192

    # --- Ingestion ----------------------------------------------------------
    chunk_size: int = 1000  # caractères
    chunk_overlap: int = 150
    fts_config: str = "english"  # configuration full-text PostgreSQL

    # --- Recherche / garde-fous -------------------------------------------
    top_k: int = 6
    candidates: int = 30
    # Similarité cosinus minimale du meilleur passage pour tenter une réponse.
    # None = seuil par défaut du fournisseur d'embeddings (calibré sur eval/).
    min_similarity: float | None = None
    # Part minimale de phrases citées dans une réponse générée.
    min_citation_coverage: float = 0.6
    contradiction_pair_similarity: float | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
