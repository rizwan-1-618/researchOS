from __future__ import annotations

import httpx

from app.config import settings
from app.integrations.http import request_json
from app.integrations.identifiers import canonical_doi, openalex_short_id
from app.integrations.types import ExternalAuthor, ExternalPaper

SOURCE = "openalex"


def abstract_from_inverted_index(inverted: dict | None) -> str | None:
    if not inverted:
        return None
    positions: list[tuple[int, str]] = []
    for word, indexes in inverted.items():
        if not isinstance(indexes, list):
            continue
        for index in indexes:
            if isinstance(index, int):
                positions.append((index, str(word)))
    if not positions:
        return None
    positions.sort(key=lambda item: item[0])
    text = " ".join(word for _, word in positions).strip()
    return text or None


def _pdf_url(work: dict) -> str | None:
    locations = [
        (work.get("primary_location") or {}).get("pdf_url"),
        (work.get("best_oa_location") or {}).get("pdf_url"),
        (work.get("open_access") or {}).get("oa_url"),
    ]
    for value in locations:
        if isinstance(value, str) and value:
            return value
    return None


def _map_work(work: dict) -> ExternalPaper | None:
    title = work.get("display_name")
    openalex_id = openalex_short_id(work.get("id"))
    if not isinstance(title, str) or not title.strip() or not openalex_id:
        return None
    authors: list[ExternalAuthor] = []
    for authorship in work.get("authorships") or []:
        author = authorship.get("author") or {}
        name = author.get("display_name")
        if not isinstance(name, str) or not name.strip():
            continue
        institutions = authorship.get("institutions") or []
        affiliation = None
        if institutions and isinstance(institutions[0], dict):
            affiliation = institutions[0].get("display_name")
        authors.append(
            ExternalAuthor(
                name=name.strip(),
                affiliation=affiliation if isinstance(affiliation, str) else None,
                openalex_id=openalex_short_id(author.get("id")),
            )
        )
    topics: list[tuple[str, str | None]] = []
    for topic in work.get("topics") or []:
        name = topic.get("display_name")
        if isinstance(name, str) and name.strip():
            topics.append((name.strip(), openalex_short_id(topic.get("id"))))
    venue = None
    source = (work.get("primary_location") or {}).get("source") or {}
    if isinstance(source, dict) and isinstance(source.get("display_name"), str):
        venue = source["display_name"]
    year = work.get("publication_year")
    cited = work.get("cited_by_count")
    landing = (work.get("primary_location") or {}).get("landing_page_url")
    ids = work.get("ids") or {}
    doi = canonical_doi(work.get("doi") if isinstance(work.get("doi"), str) else ids.get("doi"))
    references = [openalex_short_id(item) for item in work.get("referenced_works") or []]
    return ExternalPaper(
        source=SOURCE,
        external_id=openalex_id,
        title=title.strip(),
        abstract=abstract_from_inverted_index(work.get("abstract_inverted_index")),
        publication=venue,
        year=year if isinstance(year, int) else None,
        doi=doi,
        pdf_url=_pdf_url(work),
        landing_url=landing if isinstance(landing, str) else None,
        authors=authors,
        topics=topics,
        citation_count=cited if isinstance(cited, int) else None,
        openalex_id=openalex_id,
        referenced_openalex_ids=[item for item in references if item],
    )


def _params(extra: dict) -> dict:
    params = {"mailto": settings.contact_email} if settings.contact_email else {}
    params.update(extra)
    return params


async def search_top(http: httpx.AsyncClient, query: str, *, per_page: int) -> list[ExternalPaper]:
    data = await request_json(
        http,
        SOURCE,
        f"{settings.openalex_base}/works",
        params=_params({"search": query, "sort": "cited_by_count:desc", "per-page": per_page}),
    )
    papers = []
    for work in data.get("results") or []:
        mapped = _map_work(work)
        if mapped:
            papers.append(mapped)
    return papers


async def citing_works(
    http: httpx.AsyncClient,
    openalex_id: str,
    *,
    per_page: int,
    topic_id: str | None = None,
) -> list[ExternalPaper]:
    work_filter = f"cites:{openalex_short_id(openalex_id) or openalex_id}"
    if topic_id:
        work_filter = f"{work_filter},primary_topic.id:{topic_id}"
    data = await request_json(
        http,
        SOURCE,
        f"{settings.openalex_base}/works",
        params=_params({"filter": work_filter, "sort": "cited_by_count:desc", "per-page": per_page}),
    )
    papers = []
    for work in data.get("results") or []:
        mapped = _map_work(work)
        if mapped:
            papers.append(mapped)
    return papers


async def search_works(
    http: httpx.AsyncClient,
    query: str,
    *,
    page: int,
    per_page: int,
    year_from: int | None = None,
    year_to: int | None = None,
    author: str | None = None,
) -> list[ExternalPaper]:
    filters = []
    if year_from is not None or year_to is not None:
        start = year_from if year_from is not None else 1
        end = year_to if year_to is not None else 3000
        filters.append(f"publication_year:{start}-{end}")
    if author:
        filters.append(f"authorships.author.display_name.search:{author}")
    data = await request_json(
        http,
        SOURCE,
        f"{settings.openalex_base}/works",
        params=_params(
            {
                "search": query,
                "page": page,
                "per-page": per_page,
                "filter": ",".join(filters) if filters else None,
            }
        ),
    )
    papers = []
    for work in data.get("results") or []:
        mapped = _map_work(work)
        if mapped:
            papers.append(mapped)
    return papers


async def get_work(http: httpx.AsyncClient, openalex_id: str) -> ExternalPaper:
    short = openalex_short_id(openalex_id) or openalex_id
    data = await request_json(
        http,
        SOURCE,
        f"{settings.openalex_base}/works/{short}",
        params=_params({}),
    )
    mapped = _map_work(data)
    if mapped is None:
        raise ValueError("OpenAlex work has no title")
    return mapped


async def get_works(http: httpx.AsyncClient, openalex_ids: list[str]) -> list[ExternalPaper]:
    found: list[ExternalPaper] = []
    unique = [item for item in dict.fromkeys(openalex_ids) if item]
    for start in range(0, len(unique), settings.citation_batch_size):
        batch = unique[start : start + settings.citation_batch_size]
        data = await request_json(
            http,
            SOURCE,
            f"{settings.openalex_base}/works",
            params=_params(
                {
                    "filter": "openalex_id:" + "|".join(batch),
                    "per-page": len(batch),
                }
            ),
        )
        for work in data.get("results") or []:
            mapped = _map_work(work)
            if mapped:
                found.append(mapped)
    return found


async def get_work_by_doi(http: httpx.AsyncClient, doi: str) -> ExternalPaper | None:
    try:
        data = await request_json(
            http,
            SOURCE,
            f"{settings.openalex_base}/works/https://doi.org/{doi}",
            params=_params({}),
        )
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return _map_work(data)


async def get_work_by_arxiv(http: httpx.AsyncClient, arxiv_id: str) -> ExternalPaper | None:
    try:
        data = await request_json(
            http,
            SOURCE,
            f"{settings.openalex_base}/works/https://arxiv.org/abs/{arxiv_id}",
            params=_params({}),
        )
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return _map_work(data)
