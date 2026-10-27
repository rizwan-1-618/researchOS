from __future__ import annotations

import httpx

from app.config import settings
from app.integrations.http import request_json
from app.integrations.identifiers import canonical_arxiv_id, canonical_doi
from app.integrations.types import ExternalAuthor, ExternalPaper

SOURCE = "semantic_scholar"
SEARCH_FIELDS = ",".join(
    [
        "paperId",
        "title",
        "abstract",
        "year",
        "venue",
        "authors",
        "externalIds",
        "citationCount",
        "url",
        "openAccessPdf",
        "s2FieldsOfStudy",
    ]
)
DETAIL_FIELDS = SEARCH_FIELDS + "," + ",".join(
    [
        "references.paperId",
        "references.title",
        "references.abstract",
        "references.year",
        "references.venue",
        "references.authors",
        "references.externalIds",
        "references.citationCount",
        "references.url",
        "references.openAccessPdf",
    ]
)


def _affiliation(author: dict) -> str | None:
    affiliations = author.get("affiliations") or []
    if not affiliations:
        return None
    first = affiliations[0]
    if isinstance(first, str):
        return first
    if isinstance(first, dict):
        name = first.get("name") or first.get("displayName")
        return name if isinstance(name, str) else None
    return None


def _topics(work: dict) -> list[tuple[str, str | None]]:
    topics: list[tuple[str, str | None]] = []
    for item in work.get("s2FieldsOfStudy") or work.get("fieldsOfStudy") or []:
        if isinstance(item, str) and item.strip():
            topics.append((item.strip(), None))
        elif isinstance(item, dict):
            name = item.get("category") or item.get("name")
            if isinstance(name, str) and name.strip():
                topics.append((name.strip(), None))
    return topics


def _authors(work: dict) -> list[ExternalAuthor]:
    authors: list[ExternalAuthor] = []
    for author in work.get("authors") or []:
        if not isinstance(author, dict):
            continue
        name = author.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        author_id = author.get("authorId")
        authors.append(
            ExternalAuthor(
                name=name.strip(),
                affiliation=_affiliation(author),
                semantic_scholar_id=author_id if isinstance(author_id, str) else None,
            )
        )
    return authors


def _map_paper(work: dict, *, include_references: bool = False) -> ExternalPaper | None:
    title = work.get("title")
    paper_id = work.get("paperId")
    if not isinstance(title, str) or not title.strip() or not isinstance(paper_id, str) or not paper_id:
        return None
    external = work.get("externalIds") or {}
    doi = canonical_doi(external.get("DOI") if isinstance(external, dict) else None)
    arxiv = canonical_arxiv_id(external.get("ArXiv") if isinstance(external, dict) else None)
    pdf = (work.get("openAccessPdf") or {}).get("url") if isinstance(work.get("openAccessPdf"), dict) else None
    year = work.get("year")
    cited = work.get("citationCount")
    references: list[ExternalPaper] = []
    reference_ids: list[str] = []
    if include_references:
        for reference in work.get("references") or []:
            if not isinstance(reference, dict):
                continue
            mapped = _map_paper(reference, include_references=False)
            if mapped:
                references.append(mapped)
                reference_ids.append(mapped.external_id)
    return ExternalPaper(
        source=SOURCE,
        external_id=paper_id,
        title=title.strip(),
        abstract=work.get("abstract") if isinstance(work.get("abstract"), str) else None,
        publication=work.get("venue") if isinstance(work.get("venue"), str) else None,
        year=year if isinstance(year, int) else None,
        doi=doi,
        pdf_url=pdf if isinstance(pdf, str) else None,
        landing_url=work.get("url") if isinstance(work.get("url"), str) else None,
        authors=_authors(work),
        topics=_topics(work),
        citation_count=cited if isinstance(cited, int) else None,
        semantic_scholar_id=paper_id,
        arxiv_id=arxiv,
        referenced_semantic_scholar_ids=reference_ids,
        references=references,
    )


def _headers() -> dict[str, str]:
    if settings.semantic_scholar_api_key:
        return {"x-api-key": settings.semantic_scholar_api_key}
    return {}


async def search_works(
    http: httpx.AsyncClient,
    query: str,
    *,
    offset: int,
    limit: int,
    year_from: int | None = None,
    year_to: int | None = None,
) -> list[ExternalPaper]:
    params: dict = {"query": query, "offset": offset, "limit": limit, "fields": SEARCH_FIELDS}
    if year_from is not None:
        params["year"] = f"{year_from}-{year_to if year_to is not None else ''}"
    elif year_to is not None:
        params["year"] = f"-{year_to}"
    data = await request_json(
        http,
        SOURCE,
        f"{settings.semantic_scholar_base}/paper/search",
        params=params,
        headers=_headers(),
    )
    papers = []
    for work in data.get("data") or []:
        mapped = _map_paper(work)
        if mapped:
            papers.append(mapped)
    return papers


async def get_work(http: httpx.AsyncClient, paper_id: str) -> ExternalPaper:
    data = await request_json(
        http,
        SOURCE,
        f"{settings.semantic_scholar_base}/paper/{paper_id}",
        params={"fields": DETAIL_FIELDS},
        headers=_headers(),
    )
    mapped = _map_paper(data, include_references=True)
    if mapped is None:
        raise ValueError("Semantic Scholar paper has no title")
    return mapped
