from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ExternalAuthor:
    name: str
    affiliation: str | None = None
    openalex_id: str | None = None
    semantic_scholar_id: str | None = None


@dataclass(slots=True)
class ExternalPaper:
    source: str
    external_id: str
    title: str
    abstract: str | None = None
    publication: str | None = None
    year: int | None = None
    doi: str | None = None
    pdf_url: str | None = None
    landing_url: str | None = None
    authors: list[ExternalAuthor] = field(default_factory=list)
    topics: list[tuple[str, str | None]] = field(default_factory=list)
    citation_count: int | None = None
    openalex_id: str | None = None
    semantic_scholar_id: str | None = None
    arxiv_id: str | None = None
    referenced_openalex_ids: list[str] = field(default_factory=list)
    referenced_semantic_scholar_ids: list[str] = field(default_factory=list)
    references: list[ExternalPaper] = field(default_factory=list)
