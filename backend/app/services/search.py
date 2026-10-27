from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed_one
from app.algorithms.ranking import reciprocal_rank_fusion
from app.config import settings
from app.integrations.identifiers import canonical_doi
from app.models.entities import (
    Author,
    Collection,
    CollectionPaper,
    Highlight,
    HighlightEmbedding,
    LibraryItem,
    Note,
    NoteEmbedding,
    Paper,
    PaperAuthor,
    PaperChunk,
    PaperEmbedding,
    PaperTag,
    Project,
    ProjectPaper,
    Tag,
)
from app.models.enums import ReadingStatus, SearchMode
from app.schemas.dto import HighlightHit, NoteHit, SearchHit, SearchOut
from app.services.support import paper_cards


def _filters(
    user_id: UUID,
    *,
    status_filter: ReadingStatus | None,
    important: bool | None,
    favorite: bool | None,
    tag_id: UUID | None,
    collection_id: UUID | None,
    project_id: UUID | None,
    year_from: int | None,
    year_to: int | None,
    author: str | None,
):
    clauses = [LibraryItem.user_id == user_id]
    if status_filter is not None:
        clauses.append(LibraryItem.status == status_filter)
    if important is not None:
        clauses.append(LibraryItem.is_important == important)
    if favorite is not None:
        clauses.append(LibraryItem.is_favorite == favorite)
    if year_from is not None:
        clauses.append(Paper.year >= year_from)
    if year_to is not None:
        clauses.append(Paper.year <= year_to)
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
    if author:
        author_query = func.plainto_tsquery("english", author)
        clauses.append(
            exists(
                select(PaperAuthor.id)
                .join(Author, Author.id == PaperAuthor.author_id)
                .where(PaperAuthor.paper_id == Paper.id, Author.search_vector.op("@@")(author_query))
            )
        )
    return clauses


async def run_search(session: AsyncSession, user_id: UUID, **filters) -> SearchOut:
    query = filters.pop("query")
    mode: SearchMode = filters.pop("mode")
    limit = filters.pop("limit")
    clauses = _filters(user_id, **filters)
    keyword_rank: list[tuple[str, float]] = []
    semantic_rank: list[tuple[str, float]] = []
    snippets: dict[str, str] = {}
    if mode in {SearchMode.keyword, SearchMode.hybrid}:
        keyword_rank = await _keyword_papers(session, query, clauses)
    if mode in {SearchMode.semantic, SearchMode.hybrid}:
        vector = await asyncio.to_thread(embed_one, query)
        semantic_rank, snippets = await _semantic_papers(session, vector, clauses)
    if mode == SearchMode.hybrid:
        fused = reciprocal_rank_fusion(
            [[item for item, _score in keyword_rank], [item for item, _score in semantic_rank]],
            settings.rank_fusion_k,
        )
        ordered = fused[:limit]
    elif mode == SearchMode.keyword:
        ordered = keyword_rank[:limit]
    else:
        ordered = semantic_rank[:limit]
    papers = await _papers_in_order(session, [UUID(item) for item, _score in ordered])
    cards = {card.id: card for card in await paper_cards(session, user_id, papers)}
    paper_hits = [
        SearchHit(paper=cards[UUID(item)], score=score, snippet=snippets.get(item))
        for item, score in ordered
        if UUID(item) in cards
    ]
    note_hits = await _notes(session, user_id, query, mode, clauses)
    highlight_hits = await _highlights(session, user_id, query, mode, clauses)
    return SearchOut(papers=paper_hits, notes=note_hits[:limit], highlights=highlight_hits[:limit], mode=mode)


async def _keyword_papers(session, query: str, clauses) -> list[tuple[str, float]]:
    tsquery = func.plainto_tsquery("english", query)
    rank = func.ts_rank(Paper.search_vector, tsquery)
    text_match = or_(
        Paper.search_vector.op("@@")(tsquery),
        Paper.doi == canonical_doi(query),
        Paper.arxiv_id == query,
        Paper.openalex_id == query,
        Paper.semantic_scholar_id == query,
        exists(
            select(PaperAuthor.id)
            .join(Author, Author.id == PaperAuthor.author_id)
            .where(PaperAuthor.paper_id == Paper.id, Author.search_vector.op("@@")(tsquery))
        ),
    )
    rows = (
        await session.execute(
            select(Paper.id, rank)
            .join(LibraryItem, LibraryItem.paper_id == Paper.id)
            .where(*clauses, text_match)
            .order_by(rank.desc())
            .limit(settings.search_pool)
        )
    ).all()
    return [(str(paper_id), float(score or 0)) for paper_id, score in rows]


async def _semantic_papers(session, vector, clauses) -> tuple[list[tuple[str, float]], dict[str, str]]:
    distance = PaperEmbedding.embedding.cosine_distance(vector)
    paper_rows = (
        await session.execute(
            select(Paper.id, (1 - distance).label("score"))
            .join(PaperEmbedding, PaperEmbedding.paper_id == Paper.id)
            .join(LibraryItem, LibraryItem.paper_id == Paper.id)
            .where(*clauses)
            .order_by(distance)
            .limit(settings.search_pool)
        )
    ).all()
    chunk_distance = PaperChunk.embedding.cosine_distance(vector)
    chunk_rows = (
        await session.execute(
            select(PaperChunk.paper_id, PaperChunk.content, (1 - chunk_distance).label("score"))
            .join(LibraryItem, LibraryItem.paper_id == PaperChunk.paper_id)
            .join(Paper, Paper.id == PaperChunk.paper_id)
            .where(*clauses)
            .order_by(chunk_distance)
            .limit(settings.search_pool)
        )
    ).all()
    best: dict[str, float] = {}
    snippets: dict[str, str] = {}
    for paper_id, score in paper_rows:
        best[str(paper_id)] = float(score)
    for paper_id, content, score in chunk_rows:
        key = str(paper_id)
        value = float(score)
        if key not in best or value > best[key]:
            best[key] = value
            snippets[key] = content
        elif key not in snippets:
            snippets[key] = content
    ordered = sorted(best.items(), key=lambda item: item[1], reverse=True)
    return ordered, snippets


async def _papers_in_order(session, ids: list[UUID]):
    if not ids:
        return []
    rows = list((await session.scalars(select(Paper).where(Paper.id.in_(ids)))).all())
    by_id = {row.id: row for row in rows}
    return [by_id[item] for item in ids if item in by_id]


async def _notes(session, user_id, query, mode, clauses) -> list[NoteHit]:
    if mode == SearchMode.semantic:
        vector = await asyncio.to_thread(embed_one, query)
        distance = NoteEmbedding.embedding.cosine_distance(vector)
        rows = (
            await session.execute(
                select(Note, (1 - distance).label("score"))
                .join(NoteEmbedding, NoteEmbedding.note_id == Note.id)
                .where(Note.user_id == user_id)
                .order_by(distance)
                .limit(settings.search_pool)
            )
        ).all()
        pairs = [(note, float(score)) for note, score in rows]
    else:
        tsquery = func.plainto_tsquery("english", query)
        rank = func.ts_rank(Note.search_vector, tsquery)
        rows = (
            await session.execute(
                select(Note, rank)
                .where(Note.user_id == user_id, Note.search_vector.op("@@")(tsquery))
                .order_by(rank.desc())
                .limit(settings.search_pool)
            )
        ).all()
        pairs = [(note, float(score or 0)) for note, score in rows]
    titles = await _titles(session, [note.paper_id for note, _score in pairs if note.paper_id])
    allowed = await _allowed_paper_ids(session, clauses) if _has_paper_filters(clauses) else None
    hits = []
    for note, score in pairs:
        if allowed is not None and note.paper_id not in allowed:
            continue
        hits.append(
            NoteHit(
                id=note.id,
                content=note.content,
                score=score,
                paper_id=note.paper_id,
                paper_title=titles.get(note.paper_id),
            )
        )
    return hits


async def _highlights(session, user_id, query, mode, clauses) -> list[HighlightHit]:
    if mode == SearchMode.semantic:
        vector = await asyncio.to_thread(embed_one, query)
        distance = HighlightEmbedding.embedding.cosine_distance(vector)
        rows = (
            await session.execute(
                select(Highlight, Paper.title, (1 - distance).label("score"))
                .join(HighlightEmbedding, HighlightEmbedding.highlight_id == Highlight.id)
                .join(Paper, Paper.id == Highlight.paper_id)
                .where(Highlight.user_id == user_id)
                .order_by(distance)
                .limit(settings.search_pool)
            )
        ).all()
    else:
        tsquery = func.plainto_tsquery("english", query)
        rank = func.ts_rank(Highlight.search_vector, tsquery)
        rows = (
            await session.execute(
                select(Highlight, Paper.title, rank)
                .join(Paper, Paper.id == Highlight.paper_id)
                .where(Highlight.user_id == user_id, Highlight.search_vector.op("@@")(tsquery))
                .order_by(rank.desc())
                .limit(settings.search_pool)
            )
        ).all()
    allowed = await _allowed_paper_ids(session, clauses) if _has_paper_filters(clauses) else None
    hits = []
    for highlight, title, score in rows:
        if allowed is not None and highlight.paper_id not in allowed:
            continue
        hits.append(
            HighlightHit(
                id=highlight.id,
                paper_id=highlight.paper_id,
                paper_title=title,
                page=highlight.page,
                selected_text=highlight.selected_text,
                comment=highlight.comment,
                score=float(score or 0),
            )
        )
    return hits


def _has_paper_filters(clauses) -> bool:
    return len(clauses) > 1


async def _allowed_paper_ids(session, clauses) -> set[UUID]:
    rows = (
        await session.scalars(
            select(Paper.id).join(LibraryItem, LibraryItem.paper_id == Paper.id).where(*clauses)
        )
    ).all()
    return set(rows)


async def _titles(session, paper_ids: list[UUID]) -> dict:
    if not paper_ids:
        return {}
    return dict((await session.execute(select(Paper.id, Paper.title).where(Paper.id.in_(paper_ids)))).all())
