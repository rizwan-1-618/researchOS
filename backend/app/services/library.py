from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.crossref import get_by_doi
from app.integrations.identifiers import canonical_doi
from app.integrations.types import ExternalAuthor
from app.models.entities import (
    Author,
    Citation,
    Collection,
    CollectionPaper,
    Concept,
    Highlight,
    LibraryItem,
    Note,
    Paper,
    PaperAuthor,
    PaperConcept,
    PaperFile,
    PaperTag,
    Project,
    ProjectPaper,
    QuestionPaper,
    ResearchQuestion,
    Tag,
)
from app.models.enums import ActivityType, PaperSource, ReadingStatus
from app.schemas.dto import (
    CitationLists,
    ConceptLinkIn,
    ConceptLinkOut,
    LibraryUpdate,
    Page,
    PaperCard,
    PaperCreate,
    PaperDetail,
    PaperUpdate,
    TagIn,
    TagOut,
)
from app.services.catalog import link_record_topics, set_authors, upsert_external
from app.services.concepts import link_paper_concept
from app.services.support import (
    ensure_library,
    index_paper,
    paper_cards,
    record_event,
    require_paper,
    require_row,
)
from app.models.enums import ConceptSource

logger = logging.getLogger(__name__)


def validate_pdf(content: bytes, content_type: str | None) -> None:
    media = (content_type or "").split(";", 1)[0].strip().lower()
    if media and media not in settings.allowed_pdf_types:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Upload a PDF")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File is too large")
    if not content.startswith(settings.pdf_signature.encode("ascii")):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Upload a PDF")


async def _library_statement(user_id: UUID, status: ReadingStatus | None, important: bool | None, favorite: bool | None, tag_id: UUID | None, collection_id: UUID | None, project_id: UUID | None, q: str | None):
    clauses = [LibraryItem.user_id == user_id]
    if status is not None:
        clauses.append(LibraryItem.status == status)
    if important is not None:
        clauses.append(LibraryItem.is_important == important)
    if favorite is not None:
        clauses.append(LibraryItem.is_favorite == favorite)
    if tag_id is not None:
        clauses.append(
            exists(
                select(PaperTag.paper_id)
                .join(Tag, Tag.id == PaperTag.tag_id)
                .where(PaperTag.paper_id == Paper.id, PaperTag.tag_id == tag_id, Tag.user_id == user_id)
            )
        )
    if collection_id is not None:
        clauses.append(
            exists(
                select(CollectionPaper.paper_id)
                .join(Collection, Collection.id == CollectionPaper.collection_id)
                .where(
                    CollectionPaper.paper_id == Paper.id,
                    CollectionPaper.collection_id == collection_id,
                    Collection.user_id == user_id,
                )
            )
        )
    if project_id is not None:
        clauses.append(
            exists(
                select(ProjectPaper.paper_id)
                .join(Project, Project.id == ProjectPaper.project_id)
                .where(
                    ProjectPaper.paper_id == Paper.id,
                    ProjectPaper.project_id == project_id,
                    Project.owner_id == user_id,
                )
            )
        )
    if q:
        tsquery = func.plainto_tsquery("english", q)
        clauses.append(
            or_(
                Paper.search_vector.op("@@")(tsquery),
                Paper.doi == canonical_doi(q),
                Paper.arxiv_id == q,
                Paper.openalex_id == q,
                Paper.semantic_scholar_id == q,
                exists(
                    select(PaperAuthor.id)
                    .join(Author, Author.id == PaperAuthor.author_id)
                    .where(PaperAuthor.paper_id == Paper.id, Author.search_vector.op("@@")(tsquery))
                ),
                exists(
                    select(PaperTag.paper_id)
                    .join(Tag, Tag.id == PaperTag.tag_id)
                    .where(
                        PaperTag.paper_id == Paper.id,
                        Tag.user_id == user_id,
                        func.to_tsvector("english", Tag.name).op("@@")(tsquery),
                    )
                ),
            )
        )
    return select(Paper).join(LibraryItem, LibraryItem.paper_id == Paper.id).where(*clauses)


async def list_library(
    session: AsyncSession,
    user_id: UUID,
    *,
    limit: int,
    offset: int,
    status_filter: ReadingStatus | None,
    important: bool | None,
    favorite: bool | None,
    tag_id: UUID | None,
    collection_id: UUID | None,
    project_id: UUID | None,
    q: str | None,
) -> Page[PaperCard]:
    stmt = await _library_statement(
        user_id, status_filter, important, favorite, tag_id, collection_id, project_id, q
    )
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = list(
        (
            await session.scalars(
                stmt.order_by(LibraryItem.added_at.desc()).limit(limit).offset(offset)
            )
        ).all()
    )
    return Page(items=await paper_cards(session, user_id, rows), total=total or 0, limit=limit, offset=offset)


async def paper_detail(session: AsyncSession, user_id: UUID, paper_id: UUID) -> PaperDetail:
    paper = await require_paper(session, paper_id)
    card = (await paper_cards(session, user_id, [paper]))[0]
    concept_rows = (
        await session.execute(
            select(Concept, PaperConcept.relationship_type)
            .join(PaperConcept, PaperConcept.concept_id == Concept.id)
            .where(PaperConcept.paper_id == paper_id, PaperConcept.user_id == user_id)
            .order_by(Concept.name)
        )
    ).all()
    collection_ids = list(
        (
            await session.scalars(
                select(CollectionPaper.collection_id)
                .join(Collection, Collection.id == CollectionPaper.collection_id)
                .where(CollectionPaper.paper_id == paper_id, Collection.user_id == user_id)
            )
        ).all()
    )
    project_ids = list(
        (
            await session.scalars(
                select(ProjectPaper.project_id)
                .join(Project, Project.id == ProjectPaper.project_id)
                .where(ProjectPaper.paper_id == paper_id, Project.owner_id == user_id)
            )
        ).all()
    )
    file_row = await session.scalar(select(PaperFile).where(PaperFile.paper_id == paper_id))
    return PaperDetail(
        **card.model_dump(),
        concepts=[
            ConceptLinkOut(id=concept.id, name=concept.name, relationship_type=relationship)
            for concept, relationship in concept_rows
        ],
        collection_ids=collection_ids,
        project_ids=project_ids,
        references_count=await session.scalar(
            select(func.count()).select_from(Citation).where(Citation.citing_paper_id == paper_id)
        )
        or 0,
        cited_by_count=await session.scalar(
            select(func.count()).select_from(Citation).where(Citation.cited_paper_id == paper_id)
        )
        or 0,
        notes_count=await session.scalar(
            select(func.count()).select_from(Note).where(Note.user_id == user_id, Note.paper_id == paper_id)
        )
        or 0,
        highlights_count=await session.scalar(
            select(func.count()).select_from(Highlight).where(Highlight.user_id == user_id, Highlight.paper_id == paper_id)
        )
        or 0,
        processing_status=file_row.processing_status if file_row else None,
        processing_error=file_row.processing_error if file_row else None,
    )


async def create_manual(session: AsyncSession, http: httpx.AsyncClient, user_id: UUID, payload: PaperCreate) -> Paper:
    doi = canonical_doi(payload.doi)
    if doi:
        existing = await session.scalar(select(Paper).where(Paper.doi == doi))
        if existing:
            await ensure_library(session, user_id, existing.id)
            return existing
    enriched = await get_by_doi(http, doi) if doi else None
    if enriched and enriched.doi:
        existing = await session.scalar(select(Paper).where(Paper.doi == enriched.doi))
        if existing:
            await ensure_library(session, user_id, existing.id)
            return existing
        paper = await upsert_external(session, enriched)
        if payload.title:
            paper.title = payload.title.strip()
        if payload.abstract:
            paper.abstract = payload.abstract
        if payload.publication:
            paper.publication = payload.publication
        if payload.year:
            paper.year = payload.year
        if payload.pdf_url:
            paper.pdf_url = payload.pdf_url
        if payload.landing_url:
            paper.landing_url = payload.landing_url
        if payload.authors:
            await set_authors(
                session,
                paper,
                [ExternalAuthor(name=author.name, affiliation=author.affiliation) for author in payload.authors],
                replace=True,
            )
        await link_record_topics(session, user_id, paper.id, enriched)
    else:
        paper = Paper(
            title=payload.title.strip(),
            abstract=payload.abstract,
            publication=payload.publication,
            year=payload.year,
            doi=doi,
            pdf_url=payload.pdf_url,
            landing_url=payload.landing_url,
            source=PaperSource.manual,
        )
        session.add(paper)
        await session.flush()
        if payload.authors:
            await set_authors(
                session,
                paper,
                [ExternalAuthor(name=author.name, affiliation=author.affiliation) for author in payload.authors],
                replace=False,
            )
    await ensure_library(session, user_id, paper.id)
    await index_paper(session, paper)
    return paper


async def update_paper(session: AsyncSession, user_id: UUID, paper_id: UUID, payload: PaperUpdate) -> Paper:
    await _require_saved(session, user_id, paper_id)
    paper = await require_paper(session, paper_id)
    if "title" in payload.model_fields_set and payload.title is not None:
        paper.title = payload.title.strip()
    if "abstract" in payload.model_fields_set:
        paper.abstract = payload.abstract
    if "publication" in payload.model_fields_set:
        paper.publication = payload.publication
    if "year" in payload.model_fields_set:
        paper.year = payload.year
    if "pdf_url" in payload.model_fields_set:
        paper.pdf_url = payload.pdf_url
    if "landing_url" in payload.model_fields_set:
        paper.landing_url = payload.landing_url
    if "doi" in payload.model_fields_set:
        doi = canonical_doi(payload.doi)
        if doi and doi != paper.doi:
            conflict = await session.scalar(select(Paper).where(Paper.doi == doi, Paper.id != paper.id))
            if conflict:
                raise HTTPException(status.HTTP_409_CONFLICT, "Another paper already uses that DOI")
        paper.doi = doi
    if payload.authors is not None:
        await set_authors(
            session,
            paper,
            [ExternalAuthor(name=author.name, affiliation=author.affiliation) for author in payload.authors],
            replace=True,
        )
    await index_paper(session, paper)
    return paper


async def update_library(session: AsyncSession, user_id: UUID, paper_id: UUID, payload: LibraryUpdate) -> LibraryItem:
    item, _created = await ensure_library(session, user_id, paper_id)
    if payload.status is not None and payload.status != item.status:
        item.status = payload.status
        if payload.status == ReadingStatus.completed:
            await record_event(session, user_id, ActivityType.paper_completed, paper_id=paper_id)
    if payload.is_important is not None:
        item.is_important = payload.is_important
    if payload.is_favorite is not None:
        item.is_favorite = payload.is_favorite
    return item


async def remove_from_library(session: AsyncSession, user_id: UUID, paper_id: UUID) -> None:
    await _require_saved(session, user_id, paper_id)
    await session.execute(
        LibraryItem.__table__.delete().where(LibraryItem.user_id == user_id, LibraryItem.paper_id == paper_id)
    )
    tag_ids = select(Tag.id).where(Tag.user_id == user_id)
    await session.execute(PaperTag.__table__.delete().where(PaperTag.paper_id == paper_id, PaperTag.tag_id.in_(tag_ids)))
    collection_ids = select(Collection.id).where(Collection.user_id == user_id)
    await session.execute(
        CollectionPaper.__table__.delete().where(
            CollectionPaper.paper_id == paper_id, CollectionPaper.collection_id.in_(collection_ids)
        )
    )
    project_ids = select(Project.id).where(Project.owner_id == user_id)
    await session.execute(
        ProjectPaper.__table__.delete().where(ProjectPaper.paper_id == paper_id, ProjectPaper.project_id.in_(project_ids))
    )
    question_ids = select(ResearchQuestion.id).where(ResearchQuestion.user_id == user_id)
    await session.execute(
        QuestionPaper.__table__.delete().where(
            QuestionPaper.paper_id == paper_id, QuestionPaper.question_id.in_(question_ids)
        )
    )


async def add_tag(session: AsyncSession, user_id: UUID, paper_id: UUID, payload: TagIn) -> Tag:
    await _require_saved(session, user_id, paper_id)
    cleaned = payload.name.strip()
    tag = await session.scalar(select(Tag).where(Tag.user_id == user_id, func.lower(Tag.name) == cleaned.lower()))
    if tag is None:
        tag = Tag(user_id=user_id, name=cleaned)
        session.add(tag)
        await session.flush()
    link = await session.get(PaperTag, (paper_id, tag.id))
    if link is None:
        session.add(PaperTag(paper_id=paper_id, tag_id=tag.id))
    return tag


async def remove_tag(session: AsyncSession, user_id: UUID, paper_id: UUID, tag_id: UUID) -> None:
    await require_row(session, Tag, tag_id, user_id)
    await session.execute(PaperTag.__table__.delete().where(PaperTag.paper_id == paper_id, PaperTag.tag_id == tag_id))


async def list_tags(session: AsyncSession, user_id: UUID) -> list[TagOut]:
    rows = (await session.scalars(select(Tag).where(Tag.user_id == user_id).order_by(Tag.name))).all()
    return [TagOut(id=row.id, name=row.name) for row in rows]


async def add_concept_link(session: AsyncSession, user_id: UUID, paper_id: UUID, payload: ConceptLinkIn) -> None:
    await _require_saved(session, user_id, paper_id)
    await link_paper_concept(session, user_id, paper_id, payload.concept_id, payload.relationship_type)


async def remove_concept_link(
    session: AsyncSession, user_id: UUID, paper_id: UUID, concept_id: UUID, relationship_type
) -> None:
    await session.execute(
        PaperConcept.__table__.delete().where(
            PaperConcept.paper_id == paper_id,
            PaperConcept.concept_id == concept_id,
            PaperConcept.user_id == user_id,
            PaperConcept.relationship_type == relationship_type,
        )
    )


async def citation_lists(session: AsyncSession, user_id: UUID, paper_id: UUID) -> CitationLists:
    await require_paper(session, paper_id)
    references = list(
        (
            await session.scalars(
                select(Paper)
                .join(Citation, Citation.cited_paper_id == Paper.id)
                .where(Citation.citing_paper_id == paper_id)
            )
        ).all()
    )
    cited_by = list(
        (
            await session.scalars(
                select(Paper)
                .join(Citation, Citation.citing_paper_id == Paper.id)
                .where(Citation.cited_paper_id == paper_id)
            )
        ).all()
    )
    return CitationLists(
        references=await paper_cards(session, user_id, references),
        cited_by=await paper_cards(session, user_id, cited_by),
    )


async def mark_opened(session: AsyncSession, user_id: UUID, paper_id: UUID) -> None:
    await _require_saved(session, user_id, paper_id)
    await record_event(session, user_id, ActivityType.paper_opened, paper_id=paper_id)


async def create_upload(session: AsyncSession, user_id: UUID, file_name: str, title: str | None) -> tuple[Paper, bool]:
    supplied = bool(title and title.strip())
    resolved = title.strip() if supplied else Path(file_name).stem.strip()
    if not resolved:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A title or file name is required")
    paper = Paper(title=resolved, source=PaperSource.upload)
    session.add(paper)
    await session.flush()
    await ensure_library(session, user_id, paper.id)
    return paper, not supplied


async def _require_saved(session: AsyncSession, user_id: UUID, paper_id: UUID) -> LibraryItem:
    await require_paper(session, paper_id)
    item = await session.get(LibraryItem, (user_id, paper_id))
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper is not in your library")
    return item


async def require_saved(session: AsyncSession, user_id: UUID, paper_id: UUID) -> LibraryItem:
    return await _require_saved(session, user_id, paper_id)
