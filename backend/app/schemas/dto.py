from __future__ import annotations

from datetime import date, datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import (
    ActivityType,
    ConceptSource,
    DiscoverySource,
    EmbeddingStatus,
    PaperSource,
    ProcessingStatus,
    ProjectStatus,
    QuestionStatus,
    ReadingStatus,
    RelationshipType,
    ResearchLevel,
    SearchMode,
    TaskPriority,
    TaskStatus,
)

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class ProfileOut(BaseModel):
    research_interests: list[str]
    skills: list[str]
    preferred_topics: list[str]


class UserOut(BaseModel):
    id: UUID
    name: str
    email: str
    research_level: ResearchLevel | None
    bio: str | None
    profile: ProfileOut


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    bio: str | None = Field(default=None, max_length=8000)
    research_level: ResearchLevel | None = None


class ProfileUpdate(BaseModel):
    research_interests: list[str] = Field(default_factory=list, max_length=40)
    skills: list[str] = Field(default_factory=list, max_length=40)
    preferred_topics: list[str] = Field(default_factory=list, max_length=40)


class AuthorIn(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    affiliation: str | None = Field(default=None, max_length=500)


class AuthorOut(BaseModel):
    id: UUID
    name: str
    affiliation: str | None = None


class TagOut(BaseModel):
    id: UUID
    name: str


class TagIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class PaperCreate(BaseModel):
    title: str = Field(min_length=1, max_length=2000)
    abstract: str | None = None
    publication: str | None = Field(default=None, max_length=500)
    year: int | None = Field(default=None, ge=1, le=3000)
    doi: str | None = Field(default=None, max_length=255)
    pdf_url: str | None = None
    landing_url: str | None = None
    authors: list[AuthorIn] = Field(default_factory=list, max_length=50)


class PaperUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=2000)
    abstract: str | None = None
    publication: str | None = Field(default=None, max_length=500)
    year: int | None = Field(default=None, ge=1, le=3000)
    doi: str | None = Field(default=None, max_length=255)
    pdf_url: str | None = None
    landing_url: str | None = None
    authors: list[AuthorIn] | None = None


class LibraryUpdate(BaseModel):
    status: ReadingStatus | None = None
    is_important: bool | None = None
    is_favorite: bool | None = None


class PaperCard(BaseModel):
    id: UUID
    title: str
    abstract: str | None
    publication: str | None
    year: int | None
    doi: str | None
    pdf_url: str | None
    landing_url: str | None
    openalex_id: str | None
    semantic_scholar_id: str | None
    arxiv_id: str | None
    external_citation_count: int | None
    source: PaperSource
    embedding_status: EmbeddingStatus
    authors: list[AuthorOut]
    tags: list[TagOut]
    in_library: bool
    status: ReadingStatus | None
    is_important: bool
    is_favorite: bool
    has_file: bool


class ConceptLinkOut(BaseModel):
    id: UUID
    name: str
    relationship_type: RelationshipType


class PaperDetail(PaperCard):
    concepts: list[ConceptLinkOut]
    collection_ids: list[UUID]
    project_ids: list[UUID]
    references_count: int
    cited_by_count: int
    notes_count: int
    highlights_count: int
    processing_status: ProcessingStatus | None
    processing_error: str | None


class CitationLists(BaseModel):
    references: list[PaperCard]
    cited_by: list[PaperCard]


class Rect(BaseModel):
    x: float
    y: float
    width: float
    height: float


class HighlightIn(BaseModel):
    paper_id: UUID
    page: int = Field(ge=1)
    selected_text: str = Field(min_length=1)
    comment: str | None = None
    rects: list[Rect] = Field(default_factory=list)
    concept_ids: list[UUID] = Field(default_factory=list)
    question_ids: list[UUID] = Field(default_factory=list)


class HighlightUpdate(BaseModel):
    comment: str | None = None
    concept_ids: list[UUID] | None = None
    question_ids: list[UUID] | None = None


class HighlightOut(BaseModel):
    id: UUID
    paper_id: UUID
    page: int
    selected_text: str
    comment: str | None
    rects: list[Rect]
    concept_ids: list[UUID]
    question_ids: list[UUID]
    created_at: datetime
    indexed: bool


class NoteIn(BaseModel):
    content: str = Field(min_length=1)
    paper_id: UUID | None = None
    project_id: UUID | None = None
    highlight_id: UUID | None = None
    page: int | None = Field(default=None, ge=1)
    concept_ids: list[UUID] = Field(default_factory=list)
    question_ids: list[UUID] = Field(default_factory=list)
    related_note_ids: list[UUID] = Field(default_factory=list)


class NoteUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    paper_id: UUID | None = None
    project_id: UUID | None = None
    page: int | None = Field(default=None, ge=1)
    concept_ids: list[UUID] | None = None
    question_ids: list[UUID] | None = None
    related_note_ids: list[UUID] | None = None
    clear_paper: bool = False
    clear_project: bool = False


class NoteOut(BaseModel):
    id: UUID
    content: str
    paper_id: UUID | None
    paper_title: str | None
    project_id: UUID | None
    highlight_id: UUID | None
    page: int | None
    concept_ids: list[UUID]
    question_ids: list[UUID]
    related_note_ids: list[UUID]
    created_at: datetime
    updated_at: datetime
    indexed: bool


class CollectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    project_id: UUID | None = None


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    project_id: UUID | None = None
    clear_project: bool = False


class CollectionOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    project_id: UUID | None
    paper_count: int
    created_at: datetime
    updated_at: datetime


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: ProjectStatus = ProjectStatus.active


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: ProjectStatus | None = None


class ProjectOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: ProjectStatus
    progress: float
    paper_count: int
    note_count: int
    concept_count: int
    open_question_count: int
    task_count: int
    created_at: datetime
    updated_at: datetime


class QuestionIn(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None
    project_id: UUID | None = None
    status: QuestionStatus = QuestionStatus.draft


class QuestionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    project_id: UUID | None = None
    status: QuestionStatus | None = None
    clear_project: bool = False


class QuestionOut(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: QuestionStatus
    allowed_statuses: list[QuestionStatus]
    project_id: UUID | None
    paper_ids: list[UUID]
    concept_ids: list[UUID]
    note_count: int
    created_at: datetime
    updated_at: datetime


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    project_id: UUID | None = None
    paper_id: UUID | None = None
    question_id: UUID | None = None
    status: TaskStatus = TaskStatus.todo
    priority: TaskPriority = TaskPriority.medium
    deadline: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    project_id: UUID | None = None
    paper_id: UUID | None = None
    question_id: UUID | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    deadline: date | None = None
    clear_project: bool = False
    clear_paper: bool = False
    clear_question: bool = False
    clear_deadline: bool = False


class TaskOut(BaseModel):
    id: UUID
    title: str
    description: str | None
    project_id: UUID | None
    paper_id: UUID | None
    question_id: UUID | None
    assignee_id: UUID | None
    status: TaskStatus
    priority: TaskPriority
    deadline: date | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConceptIn(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str | None = None


class ConceptUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None


class ConceptOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    source: ConceptSource
    paper_count: int
    indexed: bool
    created_at: datetime
    updated_at: datetime


class ConceptLinkIn(BaseModel):
    concept_id: UUID
    relationship_type: RelationshipType = RelationshipType.related_to


class IdList(BaseModel):
    ids: list[UUID] = Field(min_length=1)


class DiscoveredPaper(BaseModel):
    source: str
    external_id: str
    title: str
    abstract: str | None
    publication: str | None
    year: int | None
    doi: str | None
    pdf_url: str | None
    landing_url: str | None
    authors: list[str]
    topics: list[str]
    citation_count: int | None
    library_paper_id: UUID | None = None


class SourceStatus(BaseModel):
    source: str
    count: int
    error: str | None = None


class DiscoveryOut(BaseModel):
    items: list[DiscoveredPaper]
    sources: list[SourceStatus]


class ImportIn(BaseModel):
    source: DiscoverySource
    external_id: str = Field(min_length=1, max_length=300)
    project_id: UUID | None = None
    collection_id: UUID | None = None


class SearchHit(BaseModel):
    paper: PaperCard
    score: float
    snippet: str | None = None


class NoteHit(BaseModel):
    id: UUID
    content: str
    score: float
    paper_id: UUID | None
    paper_title: str | None


class HighlightHit(BaseModel):
    id: UUID
    paper_id: UUID
    paper_title: str
    page: int
    selected_text: str
    comment: str | None
    score: float


class SearchOut(BaseModel):
    papers: list[SearchHit]
    notes: list[NoteHit]
    highlights: list[HighlightHit]
    mode: SearchMode


class RecommendationOut(BaseModel):
    paper: PaperCard
    score: float
    components: dict[str, float]


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    community: int | None = None
    pagerank: float | None = None
    data: dict


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str


class RankedNode(BaseModel):
    id: str
    label: str
    score: float


class GraphOut(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    influential: list[RankedNode]


class PathOut(BaseModel):
    nodes: list[str]


class MonthPoint(BaseModel):
    month: str
    papers_opened: int
    papers_saved: int
    notes_created: int


class WeekPoint(BaseModel):
    week: str
    count: int


class TagCount(BaseModel):
    name: str
    count: int


class ProjectProgress(BaseModel):
    id: UUID
    name: str
    progress: float
    papers: int
    notes: int
    concepts: int
    open_questions: int


class ActivityOut(BaseModel):
    id: UUID
    event_type: ActivityType
    paper_id: UUID | None
    project_id: UUID | None
    created_at: datetime


class OverviewOut(BaseModel):
    papers_saved: int
    papers_reading: int
    papers_completed: int
    notes: int
    highlights: int
    questions: int
    concepts: int
    projects: int
    tasks_open: int
    unfinished_papers: int
    reading_streak_days: int
    authors_encountered: int
    reading_to_note_rate: float | None
    question_status: dict[str, int]
    top_tags: list[TagCount]
    monthly_activity: list[MonthPoint]
    weekly_reading: list[WeekPoint]
    project_progress: list[ProjectProgress]
    recent_events: list[ActivityOut]


class AuthorProfile(BaseModel):
    id: UUID
    name: str
    affiliation: str | None
    papers: list[PaperCard]
    collaborators: list[AuthorOut]
    concepts: list[str]
    paper_count: int
    external_citation_count: int


class MetaOut(BaseModel):
    max_upload_bytes: int
    research_levels: list[str]
    reading_statuses: list[str]
    question_statuses: list[str]
    question_transitions: dict[str, list[str]]
    task_statuses: list[str]
    task_priorities: list[str]
    project_statuses: list[str]
    relationship_types: list[str]
    search_modes: list[str]
    discovery_sources: list[str]


class HealthOut(BaseModel):
    status: str
    database: str
    redis: str
