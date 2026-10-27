from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.types import ExternalAuthor, ExternalPaper
from app.models.entities import Author, Citation, Paper, PaperAuthor
from app.models.enums import ConceptSource, PaperSource
from app.services.concepts import link_topics


async def find_paper(session: AsyncSession, record: ExternalPaper) -> Paper | None:
    clauses = []
    if record.doi:
        clauses.append(Paper.doi == record.doi)
    if record.openalex_id:
        clauses.append(Paper.openalex_id == record.openalex_id)
    if record.semantic_scholar_id:
        clauses.append(Paper.semantic_scholar_id == record.semantic_scholar_id)
    if record.arxiv_id:
        clauses.append(Paper.arxiv_id == record.arxiv_id)
    if not clauses:
        return None
    rows = list((await session.scalars(select(Paper).where(or_(*clauses)))).all())
    if not rows:
        return None
    if record.doi:
        for row in rows:
            if row.doi == record.doi:
                return row
    return rows[0]


def _source(value: str) -> PaperSource:
    try:
        return PaperSource(value)
    except ValueError:
        return PaperSource.citation


def fill_paper(paper: Paper, record: ExternalPaper) -> None:
    if record.abstract and not paper.abstract:
        paper.abstract = record.abstract
    if record.publication and not paper.publication:
        paper.publication = record.publication
    if record.year and not paper.year:
        paper.year = record.year
    if record.doi and not paper.doi:
        paper.doi = record.doi
    if record.pdf_url and not paper.pdf_url:
        paper.pdf_url = record.pdf_url
    if record.landing_url and not paper.landing_url:
        paper.landing_url = record.landing_url
    if record.openalex_id and not paper.openalex_id:
        paper.openalex_id = record.openalex_id
    if record.semantic_scholar_id and not paper.semantic_scholar_id:
        paper.semantic_scholar_id = record.semantic_scholar_id
    if record.arxiv_id and not paper.arxiv_id:
        paper.arxiv_id = record.arxiv_id
    if record.citation_count is not None:
        paper.external_citation_count = record.citation_count
    if paper.source == PaperSource.citation:
        paper.source = _source(record.source)


async def ensure_author(session: AsyncSession, author: ExternalAuthor) -> Author:
    found = None
    if author.openalex_id:
        found = await session.scalar(select(Author).where(Author.openalex_id == author.openalex_id))
    if found is None and author.semantic_scholar_id:
        found = await session.scalar(
            select(Author).where(Author.semantic_scholar_id == author.semantic_scholar_id)
        )
    if found:
        return found
    row = Author(
        name=author.name,
        affiliation=author.affiliation,
        openalex_id=author.openalex_id,
        semantic_scholar_id=author.semantic_scholar_id,
    )
    try:
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError:
        if author.openalex_id:
            found = await session.scalar(select(Author).where(Author.openalex_id == author.openalex_id))
        if found is None and author.semantic_scholar_id:
            found = await session.scalar(
                select(Author).where(Author.semantic_scholar_id == author.semantic_scholar_id)
            )
        if found is None:
            raise
        return found
    return row


async def authorships_for(session: AsyncSession, paper_id: UUID) -> list[PaperAuthor]:
    return list(
        (await session.scalars(select(PaperAuthor).where(PaperAuthor.paper_id == paper_id))).all()
    )


async def set_authors(session: AsyncSession, paper: Paper, authors: list[ExternalAuthor], *, replace: bool) -> None:
    existing = await authorships_for(session, paper.id)
    if replace:
        for link in existing:
            await session.delete(link)
        await session.flush()
    elif existing:
        return
    seen: set = set()
    order = 0
    for author in authors:
        if not author.name.strip():
            continue
        row = await ensure_author(session, author)
        if row.id in seen:
            continue
        seen.add(row.id)
        session.add(PaperAuthor(paper_id=paper.id, author_id=row.id, author_order=order))
        order += 1
    await session.flush()


async def upsert_external(session: AsyncSession, record: ExternalPaper) -> Paper:
    existing = await find_paper(session, record)
    if existing:
        fill_paper(existing, record)
        if record.authors and not await authorships_for(session, existing.id):
            await set_authors(session, existing, record.authors, replace=False)
        return existing
    paper = Paper(
        title=record.title,
        abstract=record.abstract,
        publication=record.publication,
        year=record.year,
        doi=record.doi,
        pdf_url=record.pdf_url,
        landing_url=record.landing_url,
        openalex_id=record.openalex_id,
        semantic_scholar_id=record.semantic_scholar_id,
        arxiv_id=record.arxiv_id,
        external_citation_count=record.citation_count,
        source=_source(record.source),
    )
    try:
        async with session.begin_nested():
            session.add(paper)
            await session.flush()
    except IntegrityError:
        found = await find_paper(session, record)
        if found is None:
            raise
        fill_paper(found, record)
        return found
    if record.authors:
        await set_authors(session, paper, record.authors, replace=False)
    return paper


async def link_record_topics(session: AsyncSession, user_id: UUID, paper_id: UUID, record: ExternalPaper) -> None:
    try:
        source = ConceptSource(record.source)
    except ValueError:
        source = ConceptSource.user
    await link_topics(session, user_id, paper_id, record.topics, source)


async def link_citation(session: AsyncSession, citing_id: UUID, cited_id: UUID) -> None:
    if citing_id == cited_id:
        return
    if await session.get(Citation, (citing_id, cited_id)) is None:
        session.add(Citation(citing_paper_id=citing_id, cited_paper_id=cited_id))
