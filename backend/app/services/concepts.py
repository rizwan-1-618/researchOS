from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Concept, PaperConcept
from app.models.enums import ConceptSource, RelationshipType
from app.services.support import index_concept


async def ensure_concept(
    session: AsyncSession,
    user_id: UUID,
    name: str,
    *,
    description: str | None = None,
    source: ConceptSource = ConceptSource.user,
    external_id: str | None = None,
) -> Concept:
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Concept name is required")
    existing = await _find_concept(session, user_id, cleaned, source, external_id)
    if existing:
        return existing
    concept = Concept(
        user_id=user_id,
        name=cleaned,
        description=description,
        source=source,
        external_id=external_id,
    )
    try:
        async with session.begin_nested():
            session.add(concept)
            await session.flush()
    except IntegrityError:
        found = await _find_concept(session, user_id, cleaned, source, external_id)
        if found is None:
            raise
        return found
    await index_concept(session, concept)
    return concept


async def _find_concept(
    session: AsyncSession,
    user_id: UUID,
    name: str,
    source: ConceptSource,
    external_id: str | None,
) -> Concept | None:
    if external_id:
        found = await session.scalar(
            select(Concept).where(
                Concept.user_id == user_id,
                Concept.source == source,
                Concept.external_id == external_id,
            )
        )
        if found:
            return found
    return await session.scalar(
        select(Concept).where(Concept.user_id == user_id, func.lower(Concept.name) == name.lower())
    )


async def link_paper_concept(
    session: AsyncSession,
    user_id: UUID,
    paper_id: UUID,
    concept_id: UUID,
    relationship_type: RelationshipType,
) -> None:
    concept = await session.get(Concept, concept_id)
    if concept is None or concept.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Concept not found")
    key = (paper_id, concept_id, relationship_type)
    if await session.get(PaperConcept, key) is None:
        session.add(
            PaperConcept(
                paper_id=paper_id,
                concept_id=concept_id,
                relationship_type=relationship_type,
                user_id=user_id,
            )
        )


async def link_topics(
    session: AsyncSession,
    user_id: UUID,
    paper_id: UUID,
    topics: list[tuple[str, str | None]],
    source: ConceptSource,
) -> None:
    for name, external_id in topics:
        concept = await ensure_concept(
            session,
            user_id,
            name,
            source=source,
            external_id=external_id,
        )
        await link_paper_concept(session, user_id, paper_id, concept.id, RelationshipType.about)
