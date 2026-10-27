from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chunking import document_text
from app.ai.embeddings import embed_one, embed_texts
from app.algorithms.ranking import weighted_mean
from app.config import settings
from app.models.entities import (
    ActivityEvent,
    Author,
    Concept,
    ConceptEmbedding,
    HighlightEmbedding,
    LibraryItem,
    NoteEmbedding,
    Paper,
    PaperAuthor,
    PaperChunk,
    PaperEmbedding,
    PaperFile,
    PaperTag,
    ProfileEmbedding,
    ProfileTerm,
    ProjectEmbedding,
    ResearchProfile,
    Tag,
)
from app.models.enums import ActivityType, EmbeddingStatus, ProfileTermKind
from app.schemas.dto import AuthorOut, PaperCard, ProfileOut, TagOut, UserOut

logger = logging.getLogger(__name__)


async def record_event(
    session: AsyncSession,
    user_id: UUID,
    event_type: ActivityType,
    *,
    paper_id: UUID | None = None,
    project_id: UUID | None = None,
    payload: dict | None = None,
) -> None:
    session.add(
        ActivityEvent(
            user_id=user_id,
            event_type=event_type,
            paper_id=paper_id,
            project_id=project_id,
            payload=payload,
        )
    )


async def require_row(session: AsyncSession, model, object_id: UUID, user_id: UUID, field: str = "user_id"):
    row = await session.get(model, object_id)
    if row is None or getattr(row, field) != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return row


async def require_paper(session: AsyncSession, paper_id: UUID) -> Paper:
    paper = await session.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paper not found")
    return paper


async def ensure_library(session: AsyncSession, user_id: UUID, paper_id: UUID) -> tuple[LibraryItem, bool]:
    item = await session.get(LibraryItem, (user_id, paper_id))
    if item is not None:
        return item, False
    item = LibraryItem(user_id=user_id, paper_id=paper_id)
    session.add(item)
    await session.flush()
    await record_event(session, user_id, ActivityType.paper_saved, paper_id=paper_id)
    return item, True


def progress_value(task_done: int, task_total: int, papers_done: int, papers_total: int) -> float:
    score = weighted_mean(
        [
            (settings.project_progress_task_weight, task_done / task_total if task_total else None),
            (settings.project_progress_paper_weight, papers_done / papers_total if papers_total else None),
        ]
    )
    return float(score or 0)


def serialize_user(user, terms: list[ProfileTerm]) -> UserOut:
    grouped: dict[ProfileTermKind, list[str]] = {kind: [] for kind in ProfileTermKind}
    for term in terms:
        grouped[term.kind].append(term.label)
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        research_level=user.research_level,
        bio=user.bio,
        profile=ProfileOut(
            research_interests=grouped[ProfileTermKind.interest],
            skills=grouped[ProfileTermKind.skill],
            preferred_topics=grouped[ProfileTermKind.topic],
        ),
    )


async def load_terms(session: AsyncSession, user_id: UUID) -> list[ProfileTerm]:
    profile_id = await session.scalar(select(ResearchProfile.id).where(ResearchProfile.user_id == user_id))
    if profile_id is None:
        return []
    return list(
        (
            await session.scalars(
                select(ProfileTerm).where(ProfileTerm.profile_id == profile_id).order_by(ProfileTerm.kind, ProfileTerm.label)
            )
        ).all()
    )


async def paper_cards(session: AsyncSession, user_id: UUID, papers: list[Paper]) -> list[PaperCard]:
    if not papers:
        return []
    ids = [paper.id for paper in papers]
    library = {
        row.paper_id: row
        for row in (
            await session.scalars(
                select(LibraryItem).where(LibraryItem.user_id == user_id, LibraryItem.paper_id.in_(ids))
            )
        ).all()
    }
    tag_map: dict[UUID, list[TagOut]] = defaultdict(list)
    tag_rows = (
        await session.execute(
            select(PaperTag.paper_id, Tag)
            .join(Tag, Tag.id == PaperTag.tag_id)
            .where(Tag.user_id == user_id, PaperTag.paper_id.in_(ids))
            .order_by(Tag.name)
        )
    ).all()
    for paper_id, tag in tag_rows:
        tag_map[paper_id].append(TagOut(id=tag.id, name=tag.name))
    file_ids = set(
        (await session.scalars(select(PaperFile.paper_id).where(PaperFile.paper_id.in_(ids)))).all()
    )
    author_map: dict[UUID, list[AuthorOut]] = defaultdict(list)
    author_rows = (
        await session.execute(
            select(PaperAuthor.paper_id, Author)
            .join(Author, Author.id == PaperAuthor.author_id)
            .where(PaperAuthor.paper_id.in_(ids))
            .order_by(PaperAuthor.author_order)
        )
    ).all()
    for paper_id, author in author_rows:
        author_map[paper_id].append(AuthorOut(id=author.id, name=author.name, affiliation=author.affiliation))
    cards = []
    for paper in papers:
        item = library.get(paper.id)
        cards.append(
            PaperCard(
                id=paper.id,
                title=paper.title,
                abstract=paper.abstract,
                publication=paper.publication,
                year=paper.year,
                doi=paper.doi,
                pdf_url=paper.pdf_url,
                landing_url=paper.landing_url,
                openalex_id=paper.openalex_id,
                semantic_scholar_id=paper.semantic_scholar_id,
                arxiv_id=paper.arxiv_id,
                external_citation_count=paper.external_citation_count,
                source=paper.source,
                embedding_status=paper.embedding_status,
                authors=author_map[paper.id],
                tags=tag_map[paper.id],
                in_library=item is not None,
                status=item.status if item else None,
                is_important=bool(item and item.is_important),
                is_favorite=bool(item and item.is_favorite),
                has_file=paper.id in file_ids,
            )
        )
    return cards


def _save(model, pk_name: str, pk: UUID, vector: list[float]):
    return model(**{pk_name: pk, "embedding": vector, "model": settings.embedding_model})


async def _store_embedding(session: AsyncSession, model, pk: UUID, vector: list[float]) -> None:
    row = await session.get(model, pk)
    if row is None:
        pk_name = list(model.__table__.primary_key.columns)[0].name
        session.add(_save(model, pk_name, pk, vector))
    else:
        row.embedding = vector
        row.model = settings.embedding_model


async def index_paper(session: AsyncSession, paper: Paper) -> None:
    text = document_text(paper.title, paper.abstract)
    if not text:
        paper.embedding_status = EmbeddingStatus.ready
        return
    try:
        vector = await asyncio.to_thread(embed_one, text)
    except Exception:
        logger.exception("paper embedding failed")
        paper.embedding_status = EmbeddingStatus.failed
        return
    await _store_embedding(session, PaperEmbedding, paper.id, vector)
    paper.embedding_status = EmbeddingStatus.ready


async def replace_chunks(session: AsyncSession, paper_id: UUID, chunks: list[tuple[int, str]]) -> None:
    await session.execute(delete(PaperChunk).where(PaperChunk.paper_id == paper_id))
    if not chunks:
        return
    vectors = await asyncio.to_thread(embed_texts, [content for _, content in chunks])
    for index, ((page, content), vector) in enumerate(zip(chunks, vectors)):
        session.add(
            PaperChunk(
                paper_id=paper_id,
                chunk_index=index,
                page=page,
                content=content,
                embedding=vector,
                model=settings.embedding_model,
            )
        )


async def index_note(session: AsyncSession, note_id: UUID, content: str) -> bool:
    try:
        vector = await asyncio.to_thread(embed_one, content)
    except Exception:
        logger.exception("note embedding failed")
        return False
    await _store_embedding(session, NoteEmbedding, note_id, vector)
    return True


async def index_highlight(session: AsyncSession, highlight_id: UUID, text: str) -> bool:
    try:
        vector = await asyncio.to_thread(embed_one, text)
    except Exception:
        logger.exception("highlight embedding failed")
        return False
    await _store_embedding(session, HighlightEmbedding, highlight_id, vector)
    return True


async def index_concept(session: AsyncSession, concept: Concept) -> bool:
    text = document_text(concept.name, concept.description)
    if not text:
        return False
    try:
        vector = await asyncio.to_thread(embed_one, text)
    except Exception:
        logger.exception("concept embedding failed")
        return False
    await _store_embedding(session, ConceptEmbedding, concept.id, vector)
    return True


async def index_profile(session: AsyncSession, user_id: UUID, text: str) -> None:
    if not text.strip():
        await session.execute(delete(ProfileEmbedding).where(ProfileEmbedding.user_id == user_id))
        return
    try:
        vector = await asyncio.to_thread(embed_one, text)
    except Exception:
        logger.exception("profile embedding failed")
        return
    await _store_embedding(session, ProfileEmbedding, user_id, vector)


async def index_project(session: AsyncSession, project_id: UUID, text: str) -> None:
    if not text.strip():
        await session.execute(delete(ProjectEmbedding).where(ProjectEmbedding.project_id == project_id))
        return
    try:
        vector = await asyncio.to_thread(embed_one, text)
    except Exception:
        logger.exception("project embedding failed")
        return
    await _store_embedding(session, ProjectEmbedding, project_id, vector)


def profile_document(user, terms: list[ProfileTerm]) -> str:
    lines = [user.name]
    if user.research_level:
        lines.append(user.research_level.value)
    if user.bio:
        lines.append(user.bio)
    for kind in ProfileTermKind:
        labels = [term.label for term in terms if term.kind == kind]
        if labels:
            lines.append(", ".join(labels))
    return document_text(*lines)


def project_document(project) -> str:
    return document_text(project.name, project.description)
