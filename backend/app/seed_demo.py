from __future__ import annotations

import asyncio
from uuid import UUID

import httpx
from sqlalchemy import delete, select

from app.config import settings
from app.db import new_engine, session_factory
from app.integrations.openalex import citing_works, get_work, get_works, search_works
from app.models.entities import (
    Collection,
    CollectionPaper,
    LibraryItem,
    Note,
    Project,
    ProjectPaper,
    QuestionPaper,
    ResearchQuestion,
    Task,
    User,
)
from app.models.enums import ActivityType, QuestionStatus, ReadingStatus, TaskPriority, TaskStatus
from app.schemas.dto import ProfileUpdate, RegisterIn
from app.services.auth import register_user, replace_profile
from app.services.catalog import link_citation, link_record_topics, upsert_external
from app.services.support import ensure_library, index_note, index_paper, index_project, record_event

EMAIL = "demo@example.com"
PASSWORD = "ResearchOS-demo"
NAME = "Demo Researcher"

CLUSTERS = (
    {
        "query": "Deep Residual Learning for Image Recognition",
        "project": "Artificial intelligence",
        "description": "Highly cited machine-learning papers and the papers that cite them.",
        "collection": "Machine learning",
        "question": "Which of these papers still shape how neural networks are designed and trained?",
        "task": "Compare the architectures in the AI set",
    },
    {
        "query": "Observation of Gravitational Waves from a Binary Black Hole Merger",
        "project": "Physics",
        "description": "Highly cited physics papers and the papers that cite them.",
        "collection": "Fundamental physics",
        "question": "How do these papers connect gravity, particles, and measurement?",
        "task": "Follow the citation path through the physics set",
    },
)


async def gather_cluster(http: httpx.AsyncClient, query: str):
    ranked = await search_works(http, query, page=1, per_page=1)
    if not ranked or not ranked[0].openalex_id:
        return []
    seed = await get_work(http, ranked[0].openalex_id)
    topic_id = seed.topics[0][1] if seed.topics else None
    citing = await citing_works(http, seed.openalex_id or seed.external_id, per_page=8, topic_id=topic_id)
    referenced = await get_works(http, seed.referenced_openalex_ids[:12])
    referenced.sort(key=lambda paper: paper.citation_count or 0, reverse=True)
    chosen = []
    seen: set[str] = set()
    for paper in (seed, *citing, *referenced[:6]):
        identifier = paper.openalex_id
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        chosen.append(paper)
    return chosen


async def seed() -> None:
    engine = new_engine()
    factory = session_factory(engine)
    try:
        async with factory() as session:
            existing = await session.scalar(select(User).where(User.email == EMAIL))
            if existing is not None:
                await session.execute(delete(User).where(User.id == existing.id))
                await session.commit()
            user = await register_user(
                session,
                RegisterIn(name=NAME, email=EMAIL, password=PASSWORD),
            )
            user.research_level = user.research_level
            from app.models.enums import ResearchLevel

            user.research_level = ResearchLevel.doctoral
            user.bio = (
                "Demo desk for two literatures: machine learning, and gravitational physics. "
                "The papers, citations, and topics come from OpenAlex."
            )
            await replace_profile(
                session,
                user,
                ProfileUpdate(
                    research_interests=["Artificial intelligence", "Physics"],
                    skills=["Python", "Research methods"],
                    preferred_topics=["Machine learning", "Gravitation"],
                ),
            )
            async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as http:
                for cluster in CLUSTERS:
                    records = await gather_cluster(http, cluster["query"])
                    if not records:
                        print(f"no papers for {cluster['query']}")
                        continue
                    project = Project(
                        owner_id=user.id,
                        name=cluster["project"],
                        description=cluster["description"],
                    )
                    collection = Collection(
                        user_id=user.id,
                        name=cluster["collection"],
                        description=cluster["description"],
                    )
                    session.add(project)
                    session.add(collection)
                    await session.flush()
                    collection.project_id = project.id
                    papers = []
                    by_openalex: dict[str, UUID] = {}
                    for index, record in enumerate(records):
                        paper = await upsert_external(session, record)
                        await link_record_topics(session, user.id, paper.id, record)
                        item, _created = await ensure_library(session, user.id, paper.id)
                        item.status = (ReadingStatus.completed, ReadingStatus.reading, ReadingStatus.to_read)[index % 3]
                        if item.status == ReadingStatus.completed:
                            await record_event(session, user.id, ActivityType.paper_completed, paper_id=paper.id, project_id=project.id)
                        if index < 4:
                            item.is_important = True
                        await record_event(session, user.id, ActivityType.paper_opened, paper_id=paper.id, project_id=project.id)
                        if await session.get(ProjectPaper, (project.id, paper.id)) is None:
                            session.add(ProjectPaper(project_id=project.id, paper_id=paper.id))
                        if await session.get(CollectionPaper, (collection.id, paper.id)) is None:
                            session.add(CollectionPaper(collection_id=collection.id, paper_id=paper.id))
                        await index_paper(session, paper)
                        papers.append((paper, record))
                        if record.openalex_id:
                            by_openalex[record.openalex_id] = paper.id
                    for _paper, record in papers:
                        source_id = by_openalex.get(record.openalex_id or "")
                        if source_id is None:
                            continue
                        for cited in record.referenced_openalex_ids:
                            target_id = by_openalex.get(cited)
                            if target_id is not None:
                                await link_citation(session, source_id, target_id)
                    question = ResearchQuestion(
                        user_id=user.id,
                        project_id=project.id,
                        title=cluster["question"],
                        description=cluster["description"],
                        status=QuestionStatus.investigating,
                    )
                    session.add(question)
                    await session.flush()
                    await record_event(session, user.id, ActivityType.question_created, project_id=project.id)
                    for paper, record in papers[:4]:
                        if await session.get(QuestionPaper, (question.id, paper.id)) is None:
                            session.add(QuestionPaper(question_id=question.id, paper_id=paper.id))
                        if record.abstract:
                            note = Note(
                                user_id=user.id,
                                paper_id=paper.id,
                                project_id=project.id,
                                content=record.abstract[:900],
                            )
                            session.add(note)
                            await session.flush()
                            await index_note(session, note.id, note.content)
                            await record_event(
                                session,
                                user.id,
                                ActivityType.note_created,
                                paper_id=paper.id,
                                project_id=project.id,
                            )
                    session.add(
                        Task(
                            user_id=user.id,
                            assignee_id=user.id,
                            project_id=project.id,
                            paper_id=papers[0][0].id,
                            question_id=question.id,
                            title=cluster["task"],
                            status=TaskStatus.in_progress,
                            priority=TaskPriority.high,
                        )
                    )
                    if len(papers) > 1:
                        session.add(
                            Task(
                                user_id=user.id,
                                assignee_id=user.id,
                                project_id=project.id,
                                paper_id=papers[1][0].id,
                                question_id=question.id,
                                title=f"Finish reading {papers[1][0].title}",
                                status=TaskStatus.done,
                                priority=TaskPriority.medium,
                            )
                        )
                        await record_event(session, user.id, ActivityType.task_completed, project_id=project.id)
                    await index_project(session, project.id, f"{project.name}\n{project.description or ''}")
                    print(cluster["project"], len(papers), "papers")
                    for paper, _record in papers:
                        print(" -", paper.year, paper.title[:90])
            await session.commit()
            saved = await session.scalar(select(LibraryItem).where(LibraryItem.user_id == user.id))
            print("demo ready", EMAIL, "library item", saved is not None)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
