"""Fournisseurs d'embeddings interchangeables."""
import re
import zlib
from functools import lru_cache
from typing import Protocol

import numpy as np

from app.config import get_settings


class Embedder(Protocol):
    name: str
    dim: int
    default_min_similarity: float
    default_pair_similarity: float

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class LocalEmbedder:
    """sentence-transformers, exécuté localement (CPU). Par défaut multilingual-e5-small :
    les questions peuvent être posées en français sur une documentation en anglais."""

    default_min_similarity = 0.80  # e5 produit des similarités élevées : seuil à recalibrer (eval/)
    default_pair_similarity = 0.88

    def __init__(self, model_name: str, dim: int):
        from sentence_transformers import SentenceTransformer

        self.name = f"local:{model_name}"
        self.model = SentenceTransformer(model_name, device="cpu")
        self.dim = self.model.get_sentence_embedding_dimension()
        if self.dim != dim:
            raise RuntimeError(f"{model_name} produit des vecteurs de dimension {self.dim}, EMBEDDING_DIM={dim}")
        self._e5 = "e5" in model_name.lower()

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        return vecs.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode([f"passage: {t}" if self._e5 else t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._encode([f"query: {text}" if self._e5 else text])[0]


_TOKEN = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)*")
_STOP = set(
    "a an the of to in on for and or is are be by with at as from that this these those it its "
    "what which when where how who shall should must may can not no do does any all each per "
    "le la les de des du un une et ou en au aux pour par sur dans quel quelle quels quelles est sont".split()
)


class HashingEmbedder:
    """Embeddings lexicaux déterministes (feature hashing de mots + n-grammes de caractères).

    Aucun téléchargement : sert aux tests, à la CI et à une démo hors-ligne. Ne capture pas
    la synonymie ni le multilingue — c'est la baseline à battre par le modèle neuronal."""

    default_min_similarity = 0.12
    default_pair_similarity = 0.45

    def __init__(self, dim: int):
        self.name = "hashing"
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        v = np.zeros(self.dim, dtype=np.float32)
        tokens = [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]
        feats = [(f"w:{t}", 1.0) for t in tokens]
        feats += [(f"b:{a}_{b}", 0.7) for a, b in zip(tokens, tokens[1:])]
        for t in tokens:
            padded = f"#{t}#"
            feats += [(f"c:{padded[i:i + 4]}", 0.25) for i in range(max(1, len(padded) - 3))]
        for f, w in feats:
            h = zlib.crc32(f.encode())
            v[h % self.dim] += w if (h >> 31) & 1 else -w
        norm = np.linalg.norm(v)
        return (v / norm if norm else v).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if s.embedding_provider == "hashing":
        return HashingEmbedder(s.embedding_dim)
    if s.embedding_provider == "local":
        return LocalEmbedder(s.embedding_model, s.embedding_dim)
    raise ValueError(f"EMBEDDING_PROVIDER inconnu : {s.embedding_provider}")
