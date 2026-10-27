from __future__ import annotations

import hashlib
import threading

import httpx

from app.ai.chunking import fit_embedding_input
from app.algorithms.vectors import normalize
from app.config import settings

_model = None
_lock = threading.Lock()


def _as_list(vector) -> list[float]:
    raw = vector.tolist() if hasattr(vector, "tolist") else vector
    return [float(value) for value in raw]


def _fake_embed(texts: list[str]) -> list[list[float]]:
    width = settings.embedding_dimensions
    vectors: list[list[float]] = []
    for text in texts:
        values: list[float] = []
        counter = 0
        seed = text.encode()
        while len(values) < width:
            digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
            values.extend((byte / 127.5) - 1 for byte in digest)
            counter += 1
        vectors.append(normalize(values[:width]))
    return vectors


def _openai_embed(texts: list[str]) -> list[list[float]]:
    response = httpx.post(
        settings.embedding_api_base.rstrip("/") + "/embeddings",
        headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
        json={"model": settings.embedding_api_model, "input": texts},
        timeout=settings.http_timeout_seconds,
    )
    response.raise_for_status()
    ordered = sorted(response.json()["data"], key=lambda item: item["index"])
    vectors = [normalize(_as_list(item["embedding"])) for item in ordered]
    if any(len(vector) != settings.embedding_dimensions for vector in vectors):
        raise RuntimeError("Embedding dimensions do not match EMBEDDING_DIMENSIONS")
    return vectors


def _fastembed_model():
    global _model
    with _lock:
        if _model is None:
            from fastembed import TextEmbedding

            _model = TextEmbedding(model_name=settings.embedding_model)
        return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    fitted = [fit_embedding_input(text) for text in texts if text and text.strip()]
    if len(fitted) != len(texts):
        raise ValueError("Cannot embed empty text")
    if not fitted:
        return []
    if settings.embedding_provider == "fake":
        vectors = _fake_embed(fitted)
    elif settings.embedding_provider == "openai":
        vectors = _openai_embed(fitted)
    else:
        vectors = [normalize(_as_list(vector)) for vector in _fastembed_model().embed(fitted)]
    if any(len(vector) != settings.embedding_dimensions for vector in vectors):
        raise RuntimeError("Embedding dimensions do not match EMBEDDING_DIMENSIONS")
    return vectors


def embed_one(text: str) -> list[float]:
    return embed_texts([text])[0]
