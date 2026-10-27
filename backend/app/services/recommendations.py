from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.algorithms.vectors import cosine, mean_vector
from app.algorithms.ranking import weighted_mean
from app.config import settings
from app.models.entities import (
    Citation,
    ConceptEmbedding,
    LibraryItem,
    Paper,
    PaperConcept,
    PaperEmbedding,
    ProfileEmbedding,
    ProjectEmbedding,
)
from app.models.enums import ReadingStatus
from app.schemas.dto import RecommendationOut
from app.services.support import paper_cards


async def recommend(session: AsyncSession, redis, http, user) -> list[RecommendationOut]:
    cache_key = f"reco:{user.id}"
    cached = await redis.get(cache_key)
    if cached:
        payload = json.loads(cached)
        papers = await _load(session, [UUID(item["paper_id"]) for item in payload])
        by_id = {paper.id: paper for paper in papers}
        cards = {card.id: card for card in await paper_cards(session, user.id, list(by_id.values()))}
        results = []
        for item in payload:
            paper_id = UUID(item["paper_id"])
            if paper_id in cards and not cards[paper_id].in_library:
                results.append(
                    RecommendationOut(paper=cards[paper_id], score=item["score"], components=item["components"])
                )
        if results:
            return results[: settings.recommendation_limit]

    library_ids = set(
        (await session.scalars(select(LibraryItem.paper_id).where(LibraryItem.user_id == user.id))).all()
    )
    profile_vector = await session.scalar(select(ProfileEmbedding.embedding).where(ProfileEmbedding.user_id == user.id))
    history_vector = await _centroid(session, user.id, ReadingStatus.completed)
    library_vector = await _centroid(session, user.id, None)
    concept_vectors = list(
        (
            await session.scalars(
                select(ConceptEmbedding.embedding)
                .join(PaperConcept, PaperConcept.concept_id == ConceptEmbedding.concept_id)
                .where(PaperConcept.user_id == user.id)
            )
        ).all()
    )
    from app.models.entities import Project

    project_vectors = list(
        (
            await session.scalars(
                select(ProjectEmbedding.embedding)
                .join(Project, Project.id == ProjectEmbedding.project_id)
                .where(Project.owner_id == user.id)
            )
        ).all()
    )
    candidate_ids = await _candidates(session, user.id, library_ids, profile_vector)
    if len(candidate_ids) < settings.recommendation_min_candidates and profile_vector is not None:
        await _discover_candidates(session, http, user)
        candidate_ids = await _candidates(session, user.id, library_ids, profile_vector)
    if not candidate_ids:
        return []
    rows = (
        await session.execute(
            select(PaperEmbedding.paper_id, PaperEmbedding.embedding).where(PaperEmbedding.paper_id.in_(candidate_ids))
        )
    ).all()
    scored = []
    for paper_id, embedding in rows:
        components = _components(
            embedding, library_vector, concept_vectors, profile_vector, project_vectors, history_vector
        )
        score = weighted_mean(
            [
                (settings.recommendation_weight_semantic, components.get("semantic")),
                (settings.recommendation_weight_topic, components.get("topic")),
                (settings.recommendation_weight_interest, components.get("interest")),
                (settings.recommendation_weight_project, components.get("project")),
                (settings.recommendation_weight_history, components.get("history")),
            ]
        )
        if score is None:
            continue
        scored.append((paper_id, float(score), {key: value for key, value in components.items() if value is not None}))
    scored.sort(key=lambda item: item[1], reverse=True)
    scored = scored[: settings.recommendation_limit]
    papers = await _load(session, [paper_id for paper_id, _score, _components in scored])
    cards = {card.id: card for card in await paper_cards(session, user.id, papers)}
    results = [
        RecommendationOut(paper=cards[paper_id], score=score, components=components)
        for paper_id, score, components in scored
        if paper_id in cards
    ]
    await redis.set(
        cache_key,
        json.dumps(
            [
                {"paper_id": str(item.paper.id), "score": item.score, "components": item.components}
                for item in results
            ]
        ),
        ex=settings.recommendation_cache_ttl_seconds,
    )
    return results


def _components(embedding, library_vector, concept_vectors, profile_vector, project_vectors, history_vector):
    components = {}
    if library_vector is not None:
        components["semantic"] = cosine(embedding, library_vector)
    if concept_vectors:
        components["topic"] = max(cosine(embedding, vector) for vector in concept_vectors)
    if profile_vector is not None:
        components["interest"] = cosine(embedding, list(profile_vector))
    if project_vectors:
        components["project"] = max(cosine(embedding, list(vector)) for vector in project_vectors)
    if history_vector is not None:
        components["history"] = cosine(embedding, history_vector)
    return components


async def _centroid(session, user_id, status: ReadingStatus | None):
    stmt = (
        select(PaperEmbedding.embedding)
        .join(LibraryItem, LibraryItem.paper_id == PaperEmbedding.paper_id)
        .where(LibraryItem.user_id == user_id)
    )
    if status is not None:
        stmt = stmt.where(LibraryItem.status == status)
    vectors = [list(vector) for vector in (await session.scalars(stmt)).all()]
    return mean_vector(vectors)


async def _candidates(session, user_id, library_ids: set[UUID], profile_vector) -> list[UUID]:
    if not library_ids:
        neighbor_ids: set[UUID] = set()
    else:
        rows = (
            await session.execute(
                select(Citation.cited_paper_id, Citation.citing_paper_id).where(
                    or_(
                        Citation.citing_paper_id.in_(library_ids),
                        Citation.cited_paper_id.in_(library_ids),
                    )
                )
            )
        ).all()
        neighbor_ids = {left for pair in rows for left in pair} - library_ids
    nearest: list[UUID] = []
    if profile_vector is not None:
        distance = PaperEmbedding.embedding.cosine_distance(list(profile_vector))
        stmt = select(PaperEmbedding.paper_id).order_by(distance).limit(settings.recommendation_candidate_pool)
        if library_ids:
            stmt = stmt.where(PaperEmbedding.paper_id.not_in(library_ids))
        nearest = list((await session.scalars(stmt)).all())
    ordered = list(dict.fromkeys([*neighbor_ids, *nearest]))
    return ordered[: settings.recommendation_candidate_pool]


async def _discover_candidates(session, http, user) -> None:
    from app.services.auth import current_user_out
    from app.services.discovery import search_sources
    from app.models.enums import DiscoverySource
    from app.services.catalog import upsert_external
    from app.services.support import index_paper

    profile = await current_user_out(session, user)
    labels = profile.profile.research_interests + profile.profile.preferred_topics
    if not labels and not user.bio:
        return
    query = " ".join(labels) if labels else user.bio
    try:
        found = await search_sources(
            session,
            http,
            user.id,
            query=query,
            source=DiscoverySource.openalex,
            page=1,
            limit=settings.recommendation_discovery_limit,
            year_from=None,
            year_to=None,
            author=None,
            use_profile=False,
        )
    except Exception:
        return
    from app.integrations import openalex

    for item in found.items:
        if item.library_paper_id or item.source != "openalex":
            continue
        try:
            record = await openalex.get_work(http, item.external_id)
        except Exception:
            continue
        paper = await upsert_external(session, record)
        await index_paper(session, paper)


async def _load(session, ids: list[UUID]):
    if not ids:
        return []
    return list((await session.scalars(select(Paper).where(Paper.id.in_(ids)))).all())
