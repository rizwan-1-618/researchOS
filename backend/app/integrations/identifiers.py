from __future__ import annotations


DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)


def canonical_doi(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    lower = text.lower()
    for prefix in DOI_PREFIXES:
        if lower.startswith(prefix):
            text = text[len(prefix) :]
            lower = text.lower()
            break
    return lower or None


def canonical_arxiv_id(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    text = text.split("?", 1)[0].split("#", 1)[0]
    if "arxiv.org" in text.lower():
        text = text.rstrip("/").split("/")[-1]
    if text.lower().startswith("arxiv:"):
        text = text.split(":", 1)[1]
    head, separator, tail = text.rpartition("v")
    if separator and tail.isdigit() and head:
        return head
    return text or None


def openalex_short_id(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return text.rstrip("/").split("/")[-1]
