from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entities import (
    ActivityEvent,
    Concept,
    Highlight,
    LibraryItem,
    Note,
    PaperAuthor,
    PaperTag,
    Project,
    ResearchQuestion,
    Tag,
    Task,
)
from app.models.enums import ActivityType, QuestionStatus, ReadingStatus, TaskStatus
from app.schemas.dto import ActivityOut, MonthPoint, OverviewOut, ProjectProgress, TagCount, WeekPoint
from app.services.workspace import list_projects


def reading_streak(days: set[date], today: date) -> int:
    cursor = today if today in days else today - timedelta(days=1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


async def overview(session: AsyncSession, user_id: UUID) -> OverviewOut:
    saved = await session.scalar(select(func.count()).select_from(LibraryItem).where(LibraryItem.user_id == user_id)) or 0
    reading = await _status_count(session, user_id, ReadingStatus.reading)
    completed = await _status_count(session, user_id, ReadingStatus.completed)
    to_read = await _status_count(session, user_id, ReadingStatus.to_read)
    notes = await session.scalar(select(func.count()).select_from(Note).where(Note.user_id == user_id)) or 0
    highlights = await session.scalar(select(func.count()).select_from(Highlight).where(Highlight.user_id == user_id)) or 0
    questions = await session.scalar(
        select(func.count()).select_from(ResearchQuestion).where(ResearchQuestion.user_id == user_id)
    ) or 0
    concepts = await session.scalar(select(func.count()).select_from(Concept).where(Concept.user_id == user_id)) or 0
    projects = await session.scalar(select(func.count()).select_from(Project).where(Project.owner_id == user_id)) or 0
    tasks_open = await session.scalar(
        select(func.count()).select_from(Task).where(Task.user_id == user_id, Task.status != TaskStatus.done)
    ) or 0
    authors = await session.scalar(
        select(func.count(func.distinct(PaperAuthor.author_id)))
        .join(LibraryItem, LibraryItem.paper_id == PaperAuthor.paper_id)
        .where(LibraryItem.user_id == user_id)
    ) or 0
    completed_ids = select(LibraryItem.paper_id).where(
        LibraryItem.user_id == user_id, LibraryItem.status == ReadingStatus.completed
    )
    noted = await session.scalar(
        select(func.count(func.distinct(Note.paper_id))).where(
            Note.user_id == user_id, Note.paper_id.in_(completed_ids)
        )
    ) or 0
    rate = (noted / completed) if completed else None
    status_rows = (
        await session.execute(
            select(ResearchQuestion.status, func.count())
            .where(ResearchQuestion.user_id == user_id)
            .group_by(ResearchQuestion.status)
        )
    ).all()
    question_status = {status.value: 0 for status in QuestionStatus}
    for status, count in status_rows:
        question_status[status.value] = count
    tag_rows = (
        await session.execute(
            select(Tag.name, func.count())
            .join(PaperTag, PaperTag.tag_id == Tag.id)
            .where(Tag.user_id == user_id)
            .group_by(Tag.name)
            .order_by(func.count().desc())
            .limit(settings.analytics_top_tags)
        )
    ).all()
    today = datetime.now(UTC).date()
    start = date(today.year, today.month, 1)
    month_cursor = start
    for _ in range(settings.analytics_months - 1):
        month_cursor = (month_cursor.replace(day=1) - timedelta(days=1)).replace(day=1)
    events = (
        await session.scalars(
            select(ActivityEvent).where(ActivityEvent.user_id == user_id, ActivityEvent.created_at >= datetime.combine(month_cursor, datetime.min.time(), UTC))
        )
    ).all()
    months = _months(today, settings.analytics_months)
    month_map = {month: {"papers_opened": 0, "papers_saved": 0, "notes_created": 0} for month in months}
    weeks = _weeks(today, settings.analytics_weeks)
    week_map = {week: 0 for week in weeks}
    streak_days = set()
    for event in events:
        created = event.created_at.astimezone(UTC).date()
        month_key = created.strftime("%Y-%m")
        if month_key in month_map:
            if event.event_type == ActivityType.paper_opened:
                month_map[month_key]["papers_opened"] += 1
            elif event.event_type == ActivityType.paper_saved:
                month_map[month_key]["papers_saved"] += 1
            elif event.event_type == ActivityType.note_created:
                month_map[month_key]["notes_created"] += 1
        if event.event_type in {ActivityType.paper_opened, ActivityType.paper_completed}:
            week_key = f"{created.isocalendar().year}-W{created.isocalendar().week:02d}"
            if week_key in week_map:
                week_map[week_key] += 1
            streak_days.add(created)
    project_rows = await list_projects(session, user_id)
    recent = list(
        (
            await session.scalars(
                select(ActivityEvent)
                .where(ActivityEvent.user_id == user_id)
                .order_by(ActivityEvent.created_at.desc())
                .limit(settings.analytics_recent_events)
            )
        ).all()
    )
    return OverviewOut(
        papers_saved=saved,
        papers_reading=reading,
        papers_completed=completed,
        notes=notes,
        highlights=highlights,
        questions=questions,
        concepts=concepts,
        projects=projects,
        tasks_open=tasks_open,
        unfinished_papers=to_read + reading,
        reading_streak_days=reading_streak(streak_days, today),
        authors_encountered=authors,
        reading_to_note_rate=rate,
        question_status=question_status,
        top_tags=[TagCount(name=name, count=count) for name, count in tag_rows],
        monthly_activity=[MonthPoint(month=month, **month_map[month]) for month in months],
        weekly_reading=[WeekPoint(week=week, count=week_map[week]) for week in weeks],
        project_progress=[
            ProjectProgress(
                id=item.id,
                name=item.name,
                progress=item.progress,
                papers=item.paper_count,
                notes=item.note_count,
                concepts=item.concept_count,
                open_questions=item.open_question_count,
            )
            for item in project_rows
        ],
        recent_events=[
            ActivityOut(
                id=event.id,
                event_type=event.event_type,
                paper_id=event.paper_id,
                project_id=event.project_id,
                created_at=event.created_at,
            )
            for event in recent
        ],
    )


async def _status_count(session, user_id, reading_status: ReadingStatus) -> int:
    return (
        await session.scalar(
            select(func.count()).select_from(LibraryItem).where(
                LibraryItem.user_id == user_id, LibraryItem.status == reading_status
            )
        )
        or 0
    )


def _months(today: date, count: int) -> list[str]:
    months = []
    year, month = today.year, today.month
    for _ in range(count):
        months.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(months))


def _weeks(today: date, count: int) -> list[str]:
    weeks = []
    cursor = today
    for _ in range(count):
        iso = cursor.isocalendar()
        weeks.append(f"{iso.year}-W{iso.week:02d}")
        cursor -= timedelta(days=7)
    return list(reversed(weeks))
