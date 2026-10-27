from __future__ import annotations

from app.config import settings


def fit_embedding_input(text: str) -> str:
    limit = settings.embedding_input_characters
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit]


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    if len(cleaned) <= size:
        return [cleaned]
    step = max(size - overlap, 1)
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + size, len(cleaned))
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end == len(cleaned):
            break
        start += step
    return chunks


def document_text(*parts: str | None) -> str:
    return "\n".join(part.strip() for part in parts if part and part.strip())


def chunk_pages(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    chunks: list[tuple[int, str]] = []
    for page, text in pages:
        for piece in chunk_text(text, settings.chunk_size, settings.chunk_overlap):
            chunks.append((page, piece))
    return chunks
