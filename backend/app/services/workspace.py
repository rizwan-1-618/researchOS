from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.algorithms.transitions import TransitionError, allowed_question_statuses, assert_question_transition
from app.models.entities import (
    Collection,
    CollectionPaper,
    Concept,
    ConceptEmbedding,
    Highlight,
    HighlightConcept,
    HighlightEmbedding,
    HighlightQuestion,
    LibraryItem,
    Note,
    NoteConcept,
    NoteEmbedding,
    NoteLink,
    NoteQuestion,
    Paper,
    PaperConcept,
    Project,
    ProjectPaper,
    QuestionConcept,
    QuestionPaper,
    ResearchQuestion,
    Task,
)
from app.models.enums import ActivityType, QuestionStatus, ReadingStatus, TaskStatus
from app.schemas.dto import (
    CollectionIn,
    CollectionOut,
    CollectionUpdate,
    ConceptIn,
    ConceptOut,
    ConceptUpdate,
    HighlightIn,
    HighlightOut,
    HighlightUpdate,
    NoteIn,
    NoteOut,
    NoteUpdate,
    Page,
    ProjectIn,
    ProjectOut,
    ProjectUpdate,
    QuestionIn,
    QuestionOut,
    QuestionUpdate,
    Rect,
    TaskIn,
    TaskOut,
    TaskUpdate,
)
from app.services.concepts import ensure_concept, link_paper_concept
from app.services.library import require_saved
from app.services.support import (
    ensure_library,
    index_concept,
    index_highlight,
    index_note,
    index_project,
    progress_value,
    project_document,
    record_event,
    require_paper,
    require_row,
)


async def _project_metrics(session: AsyncSession, user_id: UUID, project_ids: list[UUID]) -> dict[UUID, dict]:
    metrics = {
        project_id: {
            "papers": 0,
            "papers_done": 0,
            "notes": 0,
            "concepts": set(),
            "open_questions": 0,
            "tasks": 0,
            "tasks_done": 0,
        }
        for project_id in project_ids
    }
    if not project_ids:
        return metrics
    paper_rows = (
        await session.execute(
            select(ProjectPaper.project_id, LibraryItem.status)
            .join(
                LibraryItem,
                (LibraryItem.paper_id == ProjectPaper.paper_id) & (LibraryItem.user_id == user_id),
                isouter=True,
            )
            .where(ProjectPaper.project_id.in_(project_ids))
        )
    ).all()
    for project_id, reading_status in paper_rows:
        metrics[project_id]["papers"] += 1
        if reading_status == ReadingStatus.completed:
            metrics[project_id]["papers_done"] += 1
    for project_id, count in (
        await session.execute(
            select(Note.project_id, func.count())
            .where(Note.user_id == user_id, Note.project_id.in_(project_ids))
            .group_by(Note.project_id)
        )
    ).all():
        metrics[project_id]["notes"] = count
    concept_rows = (
        await session.execute(
            select(ProjectPaper.project_id, PaperConcept.concept_id)
            .join(PaperConcept, PaperConcept.paper_id == ProjectPaper.paper_id)
            .where(ProjectPaper.project_id.in_(project_ids), PaperConcept.user_id == user_id)
        )
    ).all()
    for project_id, concept_id in concept_rows:
        metrics[project_id]["concepts"].add(concept_id)
    note_concepts = (
        await session.execute(
            select(Note.project_id, NoteConcept.concept_id)
            .join(NoteConcept, NoteConcept.note_id == Note.id)
            .where(Note.user_id == user_id, Note.project_id.in_(project_ids))
        )
    ).all()
    for project_id, concept_id in note_concepts:
        metrics[project_id]["concepts"].add(concept_id)
    for project_id, count in (
        await session.execute(
            select(ResearchQuestion.project_id, func.count())
            .where(
                ResearchQuestion.user_id == user_id,
                ResearchQuestion.project_id.in_(project_ids),
                ResearchQuestion.status != QuestionStatus.completed,
            )
            .group_by(ResearchQuestion.project_id)
        )
    ).all():
        metrics[project_id]["open_questions"] = count
    task_rows = (
        await session.execute(
            select(Task.project_id, Task.status).where(Task.user_id == user_id, Task.project_id.in_(project_ids))
        )
    ).all()
    for project_id, task_status in task_rows:
        metrics[project_id]["tasks"] += 1
        if task_status == TaskStatus.done:
            metrics[project_id]["tasks_done"] += 1
    return metrics


def _project_out(project: Project, metrics: dict) -> ProjectOut:
    item = metrics[project.id]
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        progress=progress_value(item["tasks_done"], item["tasks"], item["papers_done"], item["papers"]),
        paper_count=item["papers"],
        note_count=item["notes"],
        concept_count=len(item["concepts"]),
        open_question_count=item["open_questions"],
        task_count=item["tasks"],
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


async def list_projects(session: AsyncSession, user_id: UUID) -> list[ProjectOut]:
    projects = list(
        (
            await session.scalars(
                select(Project).where(Project.owner_id == user_id).order_by(Project.updated_at.desc())
            )
        ).all()
    )
    metrics = await _project_metrics(session, user_id, [project.id for project in projects])
    return [_project_out(project, metrics) for project in projects]


async def create_project(session: AsyncSession, user_id: UUID, payload: ProjectIn) -> Project:
    project = Project(
        owner_id=user_id,
        name=payload.name.strip(),
        description=payload.description,
        status=payload.status,
    )
    session.add(project)
    await session.flush()
    await index_project(session, project.id, project_document(project))
    await record_event(session, user_id, ActivityType.project_updated, project_id=project.id)
    return project


async def update_project(session: AsyncSession, user_id: UUID, project_id: UUID, payload: ProjectUpdate) -> Project:
    project = await require_row(session, Project, project_id, user_id, "owner_id")
    if payload.name is not None:
        project.name = payload.name.strip()
    if "description" in payload.model_fields_set:
        project.description = payload.description
    if payload.status is not None:
        project.status = payload.status
    await index_project(session, project.id, project_document(project))
    await record_event(session, user_id, ActivityType.project_updated, project_id=project.id)
    return project


async def delete_project(session: AsyncSession, user_id: UUID, project_id: UUID) -> None:
    project = await require_row(session, Project, project_id, user_id, "owner_id")
    await session.delete(project)


async def set_project_papers(session: AsyncSession, user_id: UUID, project_id: UUID, paper_ids: list[UUID]) -> None:
    await require_row(session, Project, project_id, user_id, "owner_id")
    for paper_id in paper_ids:
        await require_paper(session, paper_id)
        await ensure_library(session, user_id, paper_id)
        if await session.get(ProjectPaper, (project_id, paper_id)) is None:
            session.add(ProjectPaper(project_id=project_id, paper_id=paper_id))


async def remove_project_paper(session: AsyncSession, user_id: UUID, project_id: UUID, paper_id: UUID) -> None:
    await require_row(session, Project, project_id, user_id, "owner_id")
    await session.execute(
        delete(ProjectPaper).where(ProjectPaper.project_id == project_id, ProjectPaper.paper_id == paper_id)
    )


async def list_collections(session: AsyncSession, user_id: UUID) -> list[CollectionOut]:
    rows = list(
        (
            await session.scalars(
                select(Collection).where(Collection.user_id == user_id).order_by(Collection.name)
            )
        ).all()
    )
    counts = dict(
        (
            await session.execute(
                select(CollectionPaper.collection_id, func.count())
                .where(CollectionPaper.collection_id.in_([row.id for row in rows] or [UUID(int=0)]))
                .group_by(CollectionPaper.collection_id)
            )
        ).all()
    ) if rows else {}
    return [
        CollectionOut(
            id=row.id,
            name=row.name,
            description=row.description,
            project_id=row.project_id,
            paper_count=counts.get(row.id, 0),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


async def create_collection(session: AsyncSession, user_id: UUID, payload: CollectionIn) -> Collection:
    if payload.project_id:
        await require_row(session, Project, payload.project_id, user_id, "owner_id")
    row = Collection(
        user_id=user_id,
        name=payload.name.strip(),
        description=payload.description,
        project_id=payload.project_id,
    )
    session.add(row)
    await session.flush()
    return row


async def update_collection(session: AsyncSession, user_id: UUID, collection_id: UUID, payload: CollectionUpdate) -> Collection:
    row = await require_row(session, Collection, collection_id, user_id)
    if payload.name is not None:
        row.name = payload.name.strip()
    if "description" in payload.model_fields_set:
        row.description = payload.description
    if payload.clear_project:
        row.project_id = None
    elif payload.project_id is not None:
        await require_row(session, Project, payload.project_id, user_id, "owner_id")
        row.project_id = payload.project_id
    return row


async def delete_collection(session: AsyncSession, user_id: UUID, collection_id: UUID) -> None:
    row = await require_row(session, Collection, collection_id, user_id)
    await session.delete(row)


async def add_collection_papers(session: AsyncSession, user_id: UUID, collection_id: UUID, paper_ids: list[UUID]) -> None:
    await require_row(session, Collection, collection_id, user_id)
    for paper_id in paper_ids:
        await require_paper(session, paper_id)
        await ensure_library(session, user_id, paper_id)
        if await session.get(CollectionPaper, (collection_id, paper_id)) is None:
            session.add(CollectionPaper(collection_id=collection_id, paper_id=paper_id))


async def remove_collection_paper(session: AsyncSession, user_id: UUID, collection_id: UUID, paper_id: UUID) -> None:
    await require_row(session, Collection, collection_id, user_id)
    await session.execute(
        delete(CollectionPaper).where(
            CollectionPaper.collection_id == collection_id, CollectionPaper.paper_id == paper_id
        )
    )


def _question_out(question: ResearchQuestion, paper_ids: list[UUID], concept_ids: list[UUID], note_count: int) -> QuestionOut:
    return QuestionOut(
        id=question.id,
        title=question.title,
        description=question.description,
        status=question.status,
        allowed_statuses=allowed_question_statuses(question.status),
        project_id=question.project_id,
        paper_ids=paper_ids,
        concept_ids=concept_ids,
        note_count=note_count,
        created_at=question.created_at,
        updated_at=question.updated_at,
    )


async def _question_relations(session: AsyncSession, question_ids: list[UUID]):
    papers = defaultdict(list)
    concepts = defaultdict(list)
    notes = defaultdict(int)
    if not question_ids:
        return papers, concepts, notes
    for question_id, paper_id in (
        await session.execute(select(QuestionPaper.question_id, QuestionPaper.paper_id).where(QuestionPaper.question_id.in_(question_ids)))
    ).all():
        papers[question_id].append(paper_id)
    for question_id, concept_id in (
        await session.execute(
            select(QuestionConcept.question_id, QuestionConcept.concept_id).where(QuestionConcept.question_id.in_(question_ids))
        )
    ).all():
        concepts[question_id].append(concept_id)
    for question_id, count in (
        await session.execute(
            select(NoteQuestion.question_id, func.count())
            .where(NoteQuestion.question_id.in_(question_ids))
            .group_by(NoteQuestion.question_id)
        )
    ).all():
        notes[question_id] = count
    return papers, concepts, notes


async def list_questions(session: AsyncSession, user_id: UUID, project_id: UUID | None, status_filter: QuestionStatus | None) -> list[QuestionOut]:
    stmt = select(ResearchQuestion).where(ResearchQuestion.user_id == user_id)
    if project_id is not None:
        await require_row(session, Project, project_id, user_id, "owner_id")
        stmt = stmt.where(ResearchQuestion.project_id == project_id)
    if status_filter is not None:
        stmt = stmt.where(ResearchQuestion.status == status_filter)
    rows = list((await session.scalars(stmt.order_by(ResearchQuestion.updated_at.desc()))).all())
    papers, concepts, notes = await _question_relations(session, [row.id for row in rows])
    return [_question_out(row, papers[row.id], concepts[row.id], notes[row.id]) for row in rows]


async def create_question(session: AsyncSession, user_id: UUID, payload: QuestionIn) -> ResearchQuestion:
    if payload.project_id:
        await require_row(session, Project, payload.project_id, user_id, "owner_id")
    if payload.status != QuestionStatus.draft:
        try:
            assert_question_transition(QuestionStatus.draft, payload.status)
        except TransitionError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    question = ResearchQuestion(
        user_id=user_id,
        project_id=payload.project_id,
        title=payload.title.strip(),
        description=payload.description,
        status=payload.status,
    )
    session.add(question)
    await session.flush()
    await record_event(session, user_id, ActivityType.question_created, project_id=payload.project_id)
    return question


async def update_question(session: AsyncSession, user_id: UUID, question_id: UUID, payload: QuestionUpdate) -> ResearchQuestion:
    question = await require_row(session, ResearchQuestion, question_id, user_id)
    if payload.title is not None:
        question.title = payload.title.strip()
    if "description" in payload.model_fields_set:
        question.description = payload.description
    if payload.clear_project:
        question.project_id = None
    elif payload.project_id is not None:
        await require_row(session, Project, payload.project_id, user_id, "owner_id")
        question.project_id = payload.project_id
    if payload.status is not None:
        try:
            assert_question_transition(question.status, payload.status)
        except TransitionError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
        question.status = payload.status
    return question


async def delete_question(session: AsyncSession, user_id: UUID, question_id: UUID) -> None:
    question = await require_row(session, ResearchQuestion, question_id, user_id)
    await session.delete(question)


async def set_question_papers(session: AsyncSession, user_id: UUID, question_id: UUID, paper_ids: list[UUID]) -> None:
    await require_row(session, ResearchQuestion, question_id, user_id)
    for paper_id in paper_ids:
        await require_paper(session, paper_id)
        await ensure_library(session, user_id, paper_id)
        if await session.get(QuestionPaper, (question_id, paper_id)) is None:
            session.add(QuestionPaper(question_id=question_id, paper_id=paper_id))


async def remove_question_paper(session: AsyncSession, user_id: UUID, question_id: UUID, paper_id: UUID) -> None:
    await require_row(session, ResearchQuestion, question_id, user_id)
    await session.execute(
        delete(QuestionPaper).where(QuestionPaper.question_id == question_id, QuestionPaper.paper_id == paper_id)
    )


async def set_question_concepts(session: AsyncSession, user_id: UUID, question_id: UUID, concept_ids: list[UUID]) -> None:
    await require_row(session, ResearchQuestion, question_id, user_id)
    await session.execute(delete(QuestionConcept).where(QuestionConcept.question_id == question_id))
    for concept_id in concept_ids:
        await require_row(session, Concept, concept_id, user_id)
        session.add(QuestionConcept(question_id=question_id, concept_id=concept_id))


def _task_out(task: Task) -> TaskOut:
    return TaskOut(
        id=task.id,
        title=task.title,
        description=task.description,
        project_id=task.project_id,
        paper_id=task.paper_id,
        question_id=task.question_id,
        assignee_id=task.assignee_id,
        status=task.status,
        priority=task.priority,
        deadline=task.deadline,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


async def list_tasks(session: AsyncSession, user_id: UUID, project_id: UUID | None, status_filter: TaskStatus | None) -> list[TaskOut]:
    stmt = select(Task).where(Task.user_id == user_id)
    if project_id is not None:
        await require_row(session, Project, project_id, user_id, "owner_id")
        stmt = stmt.where(Task.project_id == project_id)
    if status_filter is not None:
        stmt = stmt.where(Task.status == status_filter)
    rows = (await session.scalars(stmt.order_by(Task.created_at.desc()))).all()
    return [_task_out(row) for row in rows]


async def create_task(session: AsyncSession, user_id: UUID, payload: TaskIn) -> Task:
    await _check_task_links(session, user_id, payload.project_id, payload.paper_id, payload.question_id)
    task = Task(
        user_id=user_id,
        assignee_id=user_id,
        project_id=payload.project_id,
        paper_id=payload.paper_id,
        question_id=payload.question_id,
        title=payload.title.strip(),
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        deadline=payload.deadline,
        completed_at=datetime.now(UTC) if payload.status == TaskStatus.done else None,
    )
    session.add(task)
    await session.flush()
    if task.status == TaskStatus.done:
        await record_event(session, user_id, ActivityType.task_completed, project_id=task.project_id)
    return task


async def update_task(session: AsyncSession, user_id: UUID, task_id: UUID, payload: TaskUpdate) -> Task:
    task = await require_row(session, Task, task_id, user_id)
    project_id = None if payload.clear_project else payload.project_id if payload.project_id is not None else task.project_id
    paper_id = None if payload.clear_paper else payload.paper_id if payload.paper_id is not None else task.paper_id
    question_id = None if payload.clear_question else payload.question_id if payload.question_id is not None else task.question_id
    if payload.clear_project:
        project_id = None
    if payload.clear_paper:
        paper_id = None
    if payload.clear_question:
        question_id = None
    await _check_task_links(session, user_id, project_id, paper_id, question_id)
    task.project_id = project_id
    task.paper_id = paper_id
    task.question_id = question_id
    if payload.title is not None:
        task.title = payload.title.strip()
    if "description" in payload.model_fields_set:
        task.description = payload.description
    if payload.priority is not None:
        task.priority = payload.priority
    if payload.clear_deadline:
        task.deadline = None
    elif "deadline" in payload.model_fields_set:
        task.deadline = payload.deadline
    if payload.status is not None and payload.status != task.status:
        task.status = payload.status
        if payload.status == TaskStatus.done:
            task.completed_at = datetime.now(UTC)
            await record_event(session, user_id, ActivityType.task_completed, project_id=task.project_id)
        else:
            task.completed_at = None
    return task


async def delete_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> None:
    task = await require_row(session, Task, task_id, user_id)
    await session.delete(task)


async def _check_task_links(session, user_id, project_id, paper_id, question_id) -> None:
    if project_id:
        await require_row(session, Project, project_id, user_id, "owner_id")
    if paper_id:
        await require_saved(session, user_id, paper_id)
    if question_id:
        await require_row(session, ResearchQuestion, question_id, user_id)


async def list_concepts(session: AsyncSession, user_id: UUID, q: str | None, project_id: UUID | None) -> list[ConceptOut]:
    stmt = select(Concept).where(Concept.user_id == user_id)
    if q:
        tsquery = func.plainto_tsquery("english", q)
        stmt = stmt.where(
            or_(
                func.to_tsvector("english", Concept.name).op("@@")(tsquery),
                func.lower(Concept.name) == q.lower(),
            )
        )
    if project_id is not None:
        await require_row(session, Project, project_id, user_id, "owner_id")
        paper_ids = select(ProjectPaper.paper_id).where(ProjectPaper.project_id == project_id)
        note_ids = select(Note.id).where(Note.user_id == user_id, Note.project_id == project_id)
        stmt = stmt.where(
            or_(
                Concept.id.in_(select(PaperConcept.concept_id).where(PaperConcept.paper_id.in_(paper_ids))),
                Concept.id.in_(select(NoteConcept.concept_id).where(NoteConcept.note_id.in_(note_ids))),
            )
        )
    rows = list((await session.scalars(stmt.order_by(Concept.name))).all())
    return await _concept_outs(session, rows)


async def create_concept(session: AsyncSession, user_id: UUID, payload: ConceptIn) -> Concept:
    return await ensure_concept(session, user_id, payload.name, description=payload.description)


async def update_concept(session: AsyncSession, user_id: UUID, concept_id: UUID, payload: ConceptUpdate) -> Concept:
    concept = await require_row(session, Concept, concept_id, user_id)
    if payload.name is not None:
        concept.name = payload.name.strip()
    if "description" in payload.model_fields_set:
        concept.description = payload.description
    await index_concept(session, concept)
    return concept


async def delete_concept(session: AsyncSession, user_id: UUID, concept_id: UUID) -> None:
    concept = await require_row(session, Concept, concept_id, user_id)
    await session.delete(concept)


async def _concept_outs(session: AsyncSession, rows: list[Concept]) -> list[ConceptOut]:
    if not rows:
        return []
    ids = [row.id for row in rows]
    counts = dict(
        (
            await session.execute(
                select(PaperConcept.concept_id, func.count())
                .where(PaperConcept.concept_id.in_(ids))
                .group_by(PaperConcept.concept_id)
            )
        ).all()
    )
    indexed = set((await session.scalars(select(ConceptEmbedding.concept_id).where(ConceptEmbedding.concept_id.in_(ids)))).all())
    return [
        ConceptOut(
            id=row.id,
            name=row.name,
            description=row.description,
            source=row.source,
            paper_count=counts.get(row.id, 0),
            indexed=row.id in indexed,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


async def concept_out(session: AsyncSession, concept: Concept) -> ConceptOut:
    return (await _concept_outs(session, [concept]))[0]


def _note_out(note: Note, paper_title: str | None, concept_ids, question_ids, related_ids, indexed: bool) -> NoteOut:
    return NoteOut(
        id=note.id,
        content=note.content,
        paper_id=note.paper_id,
        paper_title=paper_title,
        project_id=note.project_id,
        highlight_id=note.highlight_id,
        page=note.page,
        concept_ids=concept_ids,
        question_ids=question_ids,
        related_note_ids=related_ids,
        created_at=note.created_at,
        updated_at=note.updated_at,
        indexed=indexed,
    )


async def _decorate_notes(session: AsyncSession, notes: list[Note]) -> list[NoteOut]:
    if not notes:
        return []
    ids = [note.id for note in notes]
    paper_ids = [note.paper_id for note in notes if note.paper_id]
    titles = {}
    if paper_ids:
        titles = dict((await session.execute(select(Paper.id, Paper.title).where(Paper.id.in_(paper_ids)))).all())
    concepts = defaultdict(list)
    questions = defaultdict(list)
    related = defaultdict(list)
    for note_id, concept_id in (
        await session.execute(select(NoteConcept.note_id, NoteConcept.concept_id).where(NoteConcept.note_id.in_(ids)))
    ).all():
        concepts[note_id].append(concept_id)
    for note_id, question_id in (
        await session.execute(select(NoteQuestion.note_id, NoteQuestion.question_id).where(NoteQuestion.note_id.in_(ids)))
    ).all():
        questions[note_id].append(question_id)
    for left, right in (
        await session.execute(
            select(NoteLink.note_id, NoteLink.related_note_id).where(
                or_(NoteLink.note_id.in_(ids), NoteLink.related_note_id.in_(ids))
            )
        )
    ).all():
        if left in concepts or True:
            related[left].append(right)
            related[right].append(left)
    indexed = set((await session.scalars(select(NoteEmbedding.note_id).where(NoteEmbedding.note_id.in_(ids)))).all())
    id_set = set(ids)
    return [
        _note_out(
            note,
            titles.get(note.paper_id),
            concepts[note.id],
            questions[note.id],
            [item for item in related[note.id] if item in id_set and item != note.id],
            note.id in indexed,
        )
        for note in notes
    ]


async def list_notes(
    session: AsyncSession,
    user_id: UUID,
    *,
    limit: int,
    offset: int,
    paper_id: UUID | None,
    project_id: UUID | None,
    question_id: UUID | None,
    q: str | None,
) -> Page[NoteOut]:
    stmt = select(Note).where(Note.user_id == user_id)
    if paper_id is not None:
        stmt = stmt.where(Note.paper_id == paper_id)
    if project_id is not None:
        await require_row(session, Project, project_id, user_id, "owner_id")
        stmt = stmt.where(Note.project_id == project_id)
    if question_id is not None:
        await require_row(session, ResearchQuestion, question_id, user_id)
        stmt = stmt.where(Note.id.in_(select(NoteQuestion.note_id).where(NoteQuestion.question_id == question_id)))
    if q:
        stmt = stmt.where(Note.search_vector.op("@@")(func.plainto_tsquery("english", q)))
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = list((await session.scalars(stmt.order_by(Note.updated_at.desc()).limit(limit).offset(offset))).all())
    return Page(items=await _decorate_notes(session, rows), total=total or 0, limit=limit, offset=offset)


async def create_note(session: AsyncSession, user_id: UUID, payload: NoteIn) -> Note:
    await _validate_note_links(session, user_id, payload.paper_id, payload.project_id, payload.highlight_id, payload.concept_ids, payload.question_ids, payload.related_note_ids)
    note = Note(
        user_id=user_id,
        paper_id=payload.paper_id,
        project_id=payload.project_id,
        highlight_id=payload.highlight_id,
        page=payload.page,
        content=payload.content.strip(),
    )
    session.add(note)
    await session.flush()
    await _apply_note_links(session, user_id, note.id, payload.concept_ids, payload.question_ids, payload.related_note_ids)
    await index_note(session, note.id, note.content)
    await record_event(session, user_id, ActivityType.note_created, paper_id=note.paper_id, project_id=note.project_id)
    return note


async def update_note(session: AsyncSession, user_id: UUID, note_id: UUID, payload: NoteUpdate) -> Note:
    note = await require_row(session, Note, note_id, user_id)
    if payload.clear_paper:
        note.paper_id = None
    elif payload.paper_id is not None:
        await require_saved(session, user_id, payload.paper_id)
        note.paper_id = payload.paper_id
    if payload.clear_project:
        note.project_id = None
    elif payload.project_id is not None:
        await require_row(session, Project, payload.project_id, user_id, "owner_id")
        note.project_id = payload.project_id
    if "page" in payload.model_fields_set:
        note.page = payload.page
    if payload.content is not None:
        note.content = payload.content.strip()
        await index_note(session, note.id, note.content)
    if payload.concept_ids is not None or payload.question_ids is not None or payload.related_note_ids is not None:
        concept_ids = payload.concept_ids if payload.concept_ids is not None else await _note_concept_ids(session, note.id)
        question_ids = payload.question_ids if payload.question_ids is not None else await _note_question_ids(session, note.id)
        related_ids = (
            payload.related_note_ids
            if payload.related_note_ids is not None
            else list(
                (
                    await session.scalars(select(NoteLink.related_note_id).where(NoteLink.note_id == note.id))
                ).all()
            )
        )
        await _validate_note_links(session, user_id, None, None, None, concept_ids, question_ids, related_ids)
        await session.execute(delete(NoteConcept).where(NoteConcept.note_id == note.id))
        await session.execute(delete(NoteQuestion).where(NoteQuestion.note_id == note.id))
        await session.execute(delete(NoteLink).where(or_(NoteLink.note_id == note.id, NoteLink.related_note_id == note.id)))
        await _apply_note_links(session, user_id, note.id, concept_ids, question_ids, related_ids)
    return note


async def delete_note(session: AsyncSession, user_id: UUID, note_id: UUID) -> None:
    note = await require_row(session, Note, note_id, user_id)
    await session.delete(note)


async def _note_concept_ids(session, note_id):
    return list((await session.scalars(select(NoteConcept.concept_id).where(NoteConcept.note_id == note_id))).all())


async def _note_question_ids(session, note_id):
    return list((await session.scalars(select(NoteQuestion.question_id).where(NoteQuestion.note_id == note_id))).all())


async def _validate_note_links(session, user_id, paper_id, project_id, highlight_id, concept_ids, question_ids, related_ids) -> None:
    if paper_id:
        await require_saved(session, user_id, paper_id)
    if project_id:
        await require_row(session, Project, project_id, user_id, "owner_id")
    if highlight_id:
        highlight = await require_row(session, Highlight, highlight_id, user_id)
        if paper_id and highlight.paper_id != paper_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Highlight belongs to another paper")
    for concept_id in concept_ids:
        await require_row(session, Concept, concept_id, user_id)
    for question_id in question_ids:
        await require_row(session, ResearchQuestion, question_id, user_id)
    for related_id in related_ids:
        await require_row(session, Note, related_id, user_id)


async def _apply_note_links(session, user_id, note_id, concept_ids, question_ids, related_ids) -> None:
    for concept_id in concept_ids:
        session.add(NoteConcept(note_id=note_id, concept_id=concept_id))
    for question_id in question_ids:
        session.add(NoteQuestion(note_id=note_id, question_id=question_id))
    for related_id in related_ids:
        if related_id == note_id:
            continue
        session.add(NoteLink(note_id=note_id, related_note_id=related_id))


def _highlight_out(highlight: Highlight, concept_ids, question_ids, indexed: bool) -> HighlightOut:
    rects = [Rect(**rect) for rect in highlight.position_data or [] if isinstance(rect, dict)]
    return HighlightOut(
        id=highlight.id,
        paper_id=highlight.paper_id,
        page=highlight.page,
        selected_text=highlight.selected_text,
        comment=highlight.comment,
        rects=rects,
        concept_ids=concept_ids,
        question_ids=question_ids,
        created_at=highlight.created_at,
        indexed=indexed,
    )


async def list_highlights(session: AsyncSession, user_id: UUID, paper_id: UUID) -> list[HighlightOut]:
    await require_saved(session, user_id, paper_id)
    rows = list(
        (
            await session.scalars(
                select(Highlight)
                .where(Highlight.user_id == user_id, Highlight.paper_id == paper_id)
                .order_by(Highlight.page, Highlight.created_at)
            )
        ).all()
    )
    return await _decorate_highlights(session, rows)


async def create_highlight(session: AsyncSession, user_id: UUID, payload: HighlightIn) -> Highlight:
    await require_saved(session, user_id, payload.paper_id)
    for concept_id in payload.concept_ids:
        await require_row(session, Concept, concept_id, user_id)
    for question_id in payload.question_ids:
        await require_row(session, ResearchQuestion, question_id, user_id)
    highlight = Highlight(
        user_id=user_id,
        paper_id=payload.paper_id,
        page=payload.page,
        selected_text=payload.selected_text.strip(),
        comment=payload.comment,
        position_data=[rect.model_dump() for rect in payload.rects],
    )
    session.add(highlight)
    await session.flush()
    for concept_id in payload.concept_ids:
        session.add(HighlightConcept(highlight_id=highlight.id, concept_id=concept_id))
    for question_id in payload.question_ids:
        session.add(HighlightQuestion(highlight_id=highlight.id, question_id=question_id))
    text = highlight.selected_text if not highlight.comment else f"{highlight.selected_text}\n{highlight.comment}"
    await index_highlight(session, highlight.id, text)
    await record_event(session, user_id, ActivityType.highlight_created, paper_id=highlight.paper_id)
    return highlight


async def update_highlight(session: AsyncSession, user_id: UUID, highlight_id: UUID, payload: HighlightUpdate) -> Highlight:
    highlight = await require_row(session, Highlight, highlight_id, user_id)
    if "comment" in payload.model_fields_set:
        highlight.comment = payload.comment
        text = highlight.selected_text if not highlight.comment else f"{highlight.selected_text}\n{highlight.comment}"
        await index_highlight(session, highlight.id, text)
    if payload.concept_ids is not None:
        for concept_id in payload.concept_ids:
            await require_row(session, Concept, concept_id, user_id)
        await session.execute(delete(HighlightConcept).where(HighlightConcept.highlight_id == highlight.id))
        for concept_id in payload.concept_ids:
            session.add(HighlightConcept(highlight_id=highlight.id, concept_id=concept_id))
    if payload.question_ids is not None:
        for question_id in payload.question_ids:
            await require_row(session, ResearchQuestion, question_id, user_id)
        await session.execute(delete(HighlightQuestion).where(HighlightQuestion.highlight_id == highlight.id))
        for question_id in payload.question_ids:
            session.add(HighlightQuestion(highlight_id=highlight.id, question_id=question_id))
    return highlight


async def delete_highlight(session: AsyncSession, user_id: UUID, highlight_id: UUID) -> None:
    highlight = await require_row(session, Highlight, highlight_id, user_id)
    await session.delete(highlight)


async def _decorate_highlights(session, rows: list[Highlight]) -> list[HighlightOut]:
    if not rows:
        return []
    ids = [row.id for row in rows]
    concepts = defaultdict(list)
    questions = defaultdict(list)
    for highlight_id, concept_id in (
        await session.execute(
            select(HighlightConcept.highlight_id, HighlightConcept.concept_id).where(HighlightConcept.highlight_id.in_(ids))
        )
    ).all():
        concepts[highlight_id].append(concept_id)
    for highlight_id, question_id in (
        await session.execute(
            select(HighlightQuestion.highlight_id, HighlightQuestion.question_id).where(
                HighlightQuestion.highlight_id.in_(ids)
            )
        )
    ).all():
        questions[highlight_id].append(question_id)
    indexed = set(
        (await session.scalars(select(HighlightEmbedding.highlight_id).where(HighlightEmbedding.highlight_id.in_(ids)))).all()
    )
    return [_highlight_out(row, concepts[row.id], questions[row.id], row.id in indexed) for row in rows]


async def highlight_out(session: AsyncSession, highlight: Highlight) -> HighlightOut:
    return (await _decorate_highlights(session, [highlight]))[0]


async def note_out(session: AsyncSession, note: Note) -> NoteOut:
    return (await _decorate_notes(session, [note]))[0]


async def project_out(session: AsyncSession, user_id: UUID, project: Project) -> ProjectOut:
    metrics = await _project_metrics(session, user_id, [project.id])
    return _project_out(project, metrics)


async def collection_out(session: AsyncSession, collection: Collection) -> CollectionOut:
    count = await session.scalar(
        select(func.count()).select_from(CollectionPaper).where(CollectionPaper.collection_id == collection.id)
    )
    return CollectionOut(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        project_id=collection.project_id,
        paper_count=count or 0,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


async def question_out(session: AsyncSession, question: ResearchQuestion) -> QuestionOut:
    papers, concepts, notes = await _question_relations(session, [question.id])
    return _question_out(question, papers[question.id], concepts[question.id], notes[question.id])
