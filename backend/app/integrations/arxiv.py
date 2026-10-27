from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from app.config import settings
from app.integrations.http import request_text
from app.integrations.identifiers import canonical_arxiv_id, canonical_doi
from app.integrations.types import ExternalAuthor, ExternalPaper

SOURCE = "arxiv"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"


def _text(entry: ET.Element, name: str) -> str | None:
    node = entry.find(f"{ATOM}{name}")
    if node is None or node.text is None:
        return None
    value = " ".join(node.text.split())
    return value or None


def _map_entry(entry: ET.Element) -> ExternalPaper | None:
    title = _text(entry, "title")
    raw_id = _text(entry, "id")
    arxiv_id = canonical_arxiv_id(raw_id)
    if not title or not arxiv_id:
        return None
    authors = []
    for author in entry.findall(f"{ATOM}author"):
        name = author.findtext(f"{ATOM}name")
        if name and name.strip():
            authors.append(ExternalAuthor(name=" ".join(name.split())))
    published = _text(entry, "published") or ""
    year = int(published[:4]) if len(published) >= 4 and published[:4].isdigit() else None
    doi = canonical_doi(entry.findtext(f"{ARXIV}doi"))
    pdf_url = None
    landing = None
    for link in entry.findall(f"{ATOM}link"):
        href = link.attrib.get("href")
        if not href:
            continue
        if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
            pdf_url = href
        elif link.attrib.get("rel") == "alternate":
            landing = href
    categories = []
    primary = entry.find(f"{ARXIV}primary_category")
    if primary is not None and primary.attrib.get("term"):
        categories.append((primary.attrib["term"], None))
    return ExternalPaper(
        source=SOURCE,
        external_id=arxiv_id,
        title=title,
        abstract=_text(entry, "summary"),
        year=year,
        doi=doi,
        pdf_url=pdf_url,
        landing_url=landing,
        authors=authors,
        topics=categories,
        arxiv_id=arxiv_id,
    )


def _parse(document: str) -> list[ExternalPaper]:
    root = ET.fromstring(document)
    papers = []
    for entry in root.findall(f"{ATOM}entry"):
        mapped = _map_entry(entry)
        if mapped:
            papers.append(mapped)
    return papers


async def search_works(
    http: httpx.AsyncClient,
    query: str,
    *,
    start: int,
    limit: int,
    author: str | None = None,
) -> list[ExternalPaper]:
    search_query = f"all:{query}"
    if author:
        search_query = f"au:{author} AND {search_query}"
    document = await request_text(
        http,
        SOURCE,
        settings.arxiv_base,
        params={"search_query": search_query, "start": start, "max_results": limit},
    )
    return _parse(document)


async def get_work(http: httpx.AsyncClient, arxiv_id: str) -> ExternalPaper:
    document = await request_text(
        http,
        SOURCE,
        settings.arxiv_base,
        params={"id_list": canonical_arxiv_id(arxiv_id) or arxiv_id, "max_results": 1},
    )
    papers = _parse(document)
    if not papers:
        raise ValueError("arXiv record was not found")
    return papers[0]
