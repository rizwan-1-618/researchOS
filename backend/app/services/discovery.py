from __future__ import annotations

import asyncio
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations import arxiv, openalex, semantic_scholar
from app.integrations.http import IntegrationError
from app.integrations.types import ExternalPaper
from app.models.entities import LibraryItem, Paper, ProfileTerm
from app.models.enums import DiscoverySource, ProfileTermKind
from app.schemas.dto import DiscoveredPaper, DiscoveryOut, SourceStatus
from app.services.catalog import link_record_topics, upsert_external
from app.services.support import ensure_library, index_paper


def _priority(source: str) -> int:
    try:
        return settings.discovery_priority.index(source)
    except ValueError:
        return len(settings.discovery_priority)


def _fill(target: ExternalPaper, extra: ExternalPaper) -> None:
    for field in ("abstract", "publication", "year", "doi", "pdf_url", "landing_url", "citation_count"):
        if getattr(target, field) in (None, "") and getattr(extra, field) not in (None, ""):
            setattr(target, field, getattr(extra, field))
    if not target.authors and extra.authors:
        target.authors = extra.authors
    if extra.topics:
        seen = {name.casefold() for name, _external in target.topics}
        for topic in extra.topics:
            if topic[0].casefold() not in seen:
                target.topics.append(topic)
                seen.add(topic[0].casefold())
    target.openalex_id = target.openalex_id or extra.openalex_id
    target.semantic_scholar_id = target.semantic_scholar_id or extra.semantic_scholar_id
    target.arxiv_id = target.arxiv_id or extra.arxiv_id


def dedupe(records: list[ExternalPaper]) -> list[ExternalPaper]:
    ordered = sorted(records, key=lambda record: _priority(record.source))
    merged: list[ExternalPaper] = []
    by_doi: dict[str, ExternalPaper] = {}
    by_arxiv: dict[str, ExternalPaper] = {}
    for record in ordered:
        match = None
        if record.doi and record.doi in by_doi:
            match = by_doi[record.doi]
        elif record.arxiv_id and record.arxiv_id in by_arxiv:
            match = by_arxiv[record.arxiv_id]
        if match is None:
            merged.append(record)
            if record.doi:
                by_doi[record.doi] = record
            if record.arxiv_id:
                by_arxiv[record.arxiv_id] = record
        else:
            _fill(match, record)
            if record.doi and record.doi not in by_doi:
                by_doi[record.doi] = match
            if record.arxiv_id and record.arxiv_id not in by_arxiv:
                by_arxiv[record.arxiv_id] = match
    return merged


def _year_ok(record: ExternalPaper, year_from: int | None, year_to: int | None) -> bool:
    if record.year is None:
        return True
    if year_from is not None and record.year < year_from:
        return False
    if year_to is not None and record.year > year_to:
        return False
    return True


async def search_sources(
    session: AsyncSession,
    http: httpx.AsyncClient,
    user_id: UUID,
    *,
    query: str,
    source: DiscoverySource,
    page: int,
    limit: int,
    year_from: int | None,
    year_to: int | None,
    author: str | None,
    use_profile: bool,
) -> DiscoveryOut:
    search_query = query.strip()
    if use_profile:
        from app.models.entities import ResearchProfile

        labels = list(
            (
                await session.scalars(
                    select(ProfileTerm.label)
                    .join(ResearchProfile, ResearchProfile.id == ProfileTerm.profile_id)
                    .where(
                        ResearchProfile.user_id == user_id,
                        ProfileTerm.kind.in_([ProfileTermKind.interest, ProfileTermKind.topic]),
                    )
                )
            ).all()
        )
        if labels:
            search_query = f"{search_query} {' '.join(labels)}".strip()
    selected = (
        [DiscoverySource.openalex, DiscoverySource.semantic_scholar, DiscoverySource.arxiv]
        if source == DiscoverySource.all
        else [source]
    )
    tasks = []
    names = []
    offset = max(page - 1, 0) * limit
    for item in selected:
        names.append(item.value)
        if item == DiscoverySource.openalex:
            tasks.append(
                openalex.search_works(
                    http, search_query, page=page, per_page=limit, year_from=year_from, year_to=year_to, author=author
                )
            )
        elif item == DiscoverySource.semantic_scholar:
            s2_query = f"{search_query} {author}".strip() if author else search_query
            tasks.append(
                semantic_scholar.search_works(
                    http, s2_query, offset=offset, limit=limit, year_from=year_from, year_to=year_to
                )
            )
        else:
            tasks.append(arxiv.search_works(http, search_query, start=offset, limit=limit, author=author))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    records: list[ExternalPaper] = []
    statuses: list[SourceStatus] = []
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            statuses.append(SourceStatus(source=name, count=0, error="The source did not respond"))
            continue
        kept = [record for record in result if _year_ok(record, year_from, year_to)]
        statuses.append(SourceStatus(source=name, count=len(kept)))
        records.extend(kept)
    merged = dedupe(records)
    library_ids = await _library_matches(session, user_id, merged)
    items = [
        DiscoveredPaper(
            source=record.source,
            external_id=record.external_id,
            title=record.title,
            abstract=record.abstract,
            publication=record.publication,
            year=record.year,
            doi=record.doi,
            pdf_url=record.pdf_url,
            landing_url=record.landing_url,
            authors=[author.name for author in record.authors],
            topics=[name for name, _external in record.topics],
            citation_count=record.citation_count,
            library_paper_id=library_ids.get(_key(record)),
        )
        for record in merged
    ]
    return DiscoveryOut(items=items, sources=statuses)


def _key(record: ExternalPaper) -> str:
    return record.doi or record.arxiv_id or f"{record.source}:{record.external_id}"


async def _library_matches(session: AsyncSession, user_id: UUID, records: list[ExternalPaper]) -> dict[str, UUID]:
    dois = [record.doi for record in records if record.doi]
    arxiv_ids = [record.arxiv_id for record in records if record.arxiv_id]
    openalex_ids = [record.openalex_id for record in records if record.openalex_id]
    s2_ids = [record.semantic_scholar_id for record in records if record.semantic_scholar_id]
    clauses = []
    if dois:
        clauses.append(Paper.doi.in_(dois))
    if arxiv_ids:
        clauses.append(Paper.arxiv_id.in_(arxiv_ids))
    if openalex_ids:
        clauses.append(Paper.openalex_id.in_(openalex_ids))
    if s2_ids:
        clauses.append(Paper.semantic_scholar_id.in_(s2_ids))
    if not clauses:
        return {}
    rows = (
        await session.execute(
            select(Paper, LibraryItem.user_id)
            .join(LibraryItem, (LibraryItem.paper_id == Paper.id) & (LibraryItem.user_id == user_id))
            .where(or_(*clauses))
        )
    ).all()
    mapping: dict[str, UUID] = {}
    for paper, _user_id in rows:
        for record in records:
            if (
                (record.doi and record.doi == paper.doi)
                or (record.arxiv_id and record.arxiv_id == paper.arxiv_id)
                or (record.openalex_id and record.openalex_id == paper.openalex_id)
                or (record.semantic_scholar_id and record.semantic_scholar_id == paper.semantic_scholar_id)
            ):
                mapping[_key(record)] = paper.id
    return mapping


async def import_external(
    session: AsyncSession,
    http: httpx.AsyncClient,
    user_id: UUID,
    source: DiscoverySource,
    external_id: str,
) -> Paper:
    if source == DiscoverySource.all:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose a source to import")
    try:
        if source == DiscoverySource.openalex:
            record = await openalex.get_work(http, external_id)
        elif source == DiscoverySource.semantic_scholar:
            record = await semantic_scholar.get_work(http, external_id)
        else:
            record = await arxiv.get_work(http, external_id)
    except IntegrationError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, exc.detail) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That paper could not be found") from exc
    paper = await upsert_external(session, record)
    await link_record_topics(session, user_id, paper.id, record)
    await ensure_library(session, user_id, paper.id)
    await index_paper(session, paper)
    return paper
