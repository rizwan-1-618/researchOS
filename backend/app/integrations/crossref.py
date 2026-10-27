from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import quote

import httpx

from app.integrations.http import request_json
from app.integrations.identifiers import canonical_doi
from app.integrations.types import ExternalAuthor, ExternalPaper
from app.config import settings

SOURCE = "crossref"


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def _plain_text(value: str | None) -> str | None:
    if not value:
        return None
    parser = _TextExtractor()
    parser.feed(value)
    text = " ".join(parser.parts).strip()
    return text or None


def _year(message: dict) -> int | None:
    issued = message.get("issued") or {}
    parts = (issued.get("date-parts") or [[]])[0]
    if parts and isinstance(parts[0], int):
        return parts[0]
    return None


async def get_by_doi(http: httpx.AsyncClient, doi: str) -> ExternalPaper | None:
    canonical = canonical_doi(doi)
    if not canonical:
        return None
    try:
        data = await request_json(
            http,
            SOURCE,
            f"{settings.crossref_base}/works/{quote(canonical, safe='')}",
        )
    except Exception:
        return None
    message = data.get("message") if isinstance(data, dict) else None
    if not isinstance(message, dict):
        return None
    titles = message.get("title") or []
    title = titles[0] if titles and isinstance(titles[0], str) else None
    if not title:
        return None
    authors = []
    for author in message.get("author") or []:
        if not isinstance(author, dict):
            continue
        given = author.get("given") or ""
        family = author.get("family") or ""
        name = " ".join(part for part in (given, family) if isinstance(part, str) and part.strip()).strip()
        if not name:
            continue
        affiliations = author.get("affiliation") or []
        affiliation = None
        if affiliations and isinstance(affiliations[0], dict):
            affiliation = affiliations[0].get("name")
        authors.append(ExternalAuthor(name=name, affiliation=affiliation if isinstance(affiliation, str) else None))
    containers = message.get("container-title") or []
    pdf_url = None
    for link in message.get("link") or []:
        if isinstance(link, dict) and link.get("content-type") == "application/pdf" and link.get("URL"):
            pdf_url = link["URL"]
            break
    cited = message.get("is-referenced-by-count")
    return ExternalPaper(
        source=SOURCE,
        external_id=canonical,
        title=title,
        abstract=_plain_text(message.get("abstract") if isinstance(message.get("abstract"), str) else None),
        publication=containers[0] if containers and isinstance(containers[0], str) else None,
        year=_year(message),
        doi=canonical,
        pdf_url=pdf_url,
        landing_url=message.get("URL") if isinstance(message.get("URL"), str) else None,
        authors=authors,
        citation_count=cited if isinstance(cited, int) else None,
    )
