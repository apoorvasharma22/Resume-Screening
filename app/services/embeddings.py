from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

from app.config import get_settings
from app.logging_config import get_logger
from app.services.skills import extract_skills

log = get_logger(__name__)


def _augment(text: str) -> str:
    skills = extract_skills(text)
    return text + " " + " ".join("skill_" + s.lower().replace(" ", "_").replace("+", "p").replace("#", "sharp").replace(".", "") for s in skills)


class HashingEmbedder:
    name = "hashing-1024"
    dim = 1024
    lo, hi = 0.05, 0.45
    query_lo, query_hi = 0.07, 0.22

    def __init__(self) -> None:
        self._vec = HashingVectorizer(
            n_features=self.dim, ngram_range=(1, 2), stop_words="english", alternate_sign=False,
            norm="l2", binary=True, lowercase=True, token_pattern=r"(?u)\b[\w+#.]{2,}\b",
        )

    def encode(self, texts: list[str]) -> np.ndarray:
        return self._vec.transform([_augment(t) for t in texts]).toarray().astype(np.float32)


class TransformerEmbedder:
    dim = 384
    lo, hi = 0.15, 0.70
    query_lo, query_hi = 0.20, 0.60

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self.name = f"st:{model_name.split('/')[-1]}"
        self.dim = self._model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self._model.encode(texts, normalize_embeddings=True), dtype=np.float32)


_embedder = None


def get_embedder():
    global _embedder
    if _embedder is not None:
        return _embedder
    s = get_settings()
    if s.embedding_backend == "transformer":
        try:
            _embedder = TransformerEmbedder(s.embedding_model)
            log.info("Using transformer embeddings: %s", _embedder.name)
            return _embedder
        except Exception as exc:
            log.warning("Transformer embeddings unavailable (%s) - falling back to hashing backend", exc)
    _embedder = HashingEmbedder()
    return _embedder


def to_bytes(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_bytes(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    return float(np.dot(a, b) / (na * nb)) if na and nb else 0.0


def calibrate(cos: float, embedder=None, kind: str = "document") -> float:
    e = embedder or get_embedder()
    lo, hi = (e.query_lo, e.query_hi) if kind == "query" else (e.lo, e.hi)
    return float(min(1.0, max(0.0, (cos - lo) / (hi - lo))))

