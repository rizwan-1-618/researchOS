from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Author, Concept, Paper, PaperAuthor, PaperConcept
from app.schemas.dto import AuthorOut, AuthorProfile
from app.services.support import paper_cards


async def author_profile(session: AsyncSession, user_id: UUID, author_id: UUID) -> AuthorProfile:
    author = await session.get(Author, author_id)
    if author is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Author not found")
    papers = list(
        (
            await session.scalars(
                select(Paper)
                .join(PaperAuthor, PaperAuthor.paper_id == Paper.id)
                .where(PaperAuthor.author_id == author_id)
                .order_by(Paper.year.desc().nulls_last(), Paper.title)
            )
        ).all()
    )
    paper_ids = [paper.id for paper in papers]
    collaborators: list[AuthorOut] = []
    concepts: list[str] = []
    citations = 0
    if paper_ids:
        citations = (
            await session.scalar(select(func.coalesce(func.sum(Paper.external_citation_count), 0)).where(Paper.id.in_(paper_ids)))
            or 0
        )
        rows = (
            await session.scalars(
                select(Author)
                .join(PaperAuthor, PaperAuthor.author_id == Author.id)
                .where(PaperAuthor.paper_id.in_(paper_ids), Author.id != author_id)
                .distinct()
            )
        ).all()
        collaborators = [AuthorOut(id=row.id, name=row.name, affiliation=row.affiliation) for row in rows]
        concepts = list(
            (
                await session.scalars(
                    select(Concept.name)
                    .join(PaperConcept, PaperConcept.concept_id == Concept.id)
                    .where(PaperConcept.user_id == user_id, PaperConcept.paper_id.in_(paper_ids))
                    .distinct()
                    .order_by(Concept.name)
                )
            ).all()
        )
    return AuthorProfile(
        id=author.id,
        name=author.name,
        affiliation=author.affiliation,
        papers=await paper_cards(session, user_id, papers),
        collaborators=collaborators,
        concepts=concepts,
        paper_count=len(papers),
        external_citation_count=int(citations),
    )
