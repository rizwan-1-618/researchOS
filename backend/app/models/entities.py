from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.models.base import Base, pg_enum
from app.models.enums import (
    ActivityType,
    ConceptSource,
    EmbeddingStatus,
    PaperSource,
    ProcessingStatus,
    ProfileTermKind,
    ProjectStatus,
    QuestionStatus,
    ReadingStatus,
    RelationshipType,
    ResearchLevel,
    TaskPriority,
    TaskStatus,
)

VECTOR_DIM = settings.embedding_dimensions


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    research_level: Mapped[ResearchLevel | None] = mapped_column(pg_enum(ResearchLevel, "research_level"))
    bio: Mapped[str | None] = mapped_column(Text)


class ResearchProfile(Base):
    __tablename__ = "research_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)


class ProfileTerm(Base):
    __tablename__ = "profile_terms"
    __table_args__ = (UniqueConstraint("profile_id", "kind", "label", name="uq_profile_term"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_profiles.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ProfileTermKind] = mapped_column(pg_enum(ProfileTermKind, "profile_term_kind"), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Author(Base):
    __tablename__ = "authors"
    __table_args__ = (
        Index(
            "uq_authors_openalex",
            "openalex_id",
            unique=True,
            postgresql_where=text("openalex_id IS NOT NULL"),
        ),
        Index(
            "uq_authors_s2",
            "semantic_scholar_id",
            unique=True,
            postgresql_where=text("semantic_scholar_id IS NOT NULL"),
        ),
        Index("ix_authors_search", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    affiliation: Mapped[str | None] = mapped_column(String(500))
    openalex_id: Mapped[str | None] = mapped_column(String(80))
    semantic_scholar_id: Mapped[str | None] = mapped_column(String(80))
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(name, '') || ' ' || coalesce(affiliation, ''))",
            persisted=True,
        ),
        nullable=False,
    )


class Paper(Base, TimestampMixin):
    __tablename__ = "papers"
    __table_args__ = (
        Index("uq_papers_doi", "doi", unique=True, postgresql_where=text("doi IS NOT NULL")),
        Index(
            "uq_papers_openalex",
            "openalex_id",
            unique=True,
            postgresql_where=text("openalex_id IS NOT NULL"),
        ),
        Index(
            "uq_papers_s2",
            "semantic_scholar_id",
            unique=True,
            postgresql_where=text("semantic_scholar_id IS NOT NULL"),
        ),
        Index(
            "uq_papers_arxiv",
            "arxiv_id",
            unique=True,
            postgresql_where=text("arxiv_id IS NOT NULL"),
        ),
        Index("ix_papers_search", "search_vector", postgresql_using="gin"),
        Index("ix_papers_year", "year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text)
    publication: Mapped[str | None] = mapped_column(String(500))
    year: Mapped[int | None] = mapped_column(Integer)
    doi: Mapped[str | None] = mapped_column(String(255))
    pdf_url: Mapped[str | None] = mapped_column(Text)
    landing_url: Mapped[str | None] = mapped_column(Text)
    openalex_id: Mapped[str | None] = mapped_column(String(80))
    semantic_scholar_id: Mapped[str | None] = mapped_column(String(80))
    arxiv_id: Mapped[str | None] = mapped_column(String(80))
    external_citation_count: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[PaperSource] = mapped_column(pg_enum(PaperSource, "paper_source"), nullable=False)
    embedding_status: Mapped[EmbeddingStatus] = mapped_column(
        pg_enum(EmbeddingStatus, "embedding_status"),
        nullable=False,
        server_default=EmbeddingStatus.pending.value,
    )
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(abstract, '') || ' ' || coalesce(publication, ''))",
            persisted=True,
        ),
        nullable=False,
    )
    authorships: Mapped[list[PaperAuthor]] = relationship(
        back_populates="paper",
        cascade="all, delete-orphan",
        order_by="PaperAuthor.author_order",
        lazy="raise",
    )


class PaperAuthor(Base):
    __tablename__ = "paper_authors"
    __table_args__ = (UniqueConstraint("paper_id", "author_id", name="uq_paper_author"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("authors.id", ondelete="CASCADE"), index=True)
    author_order: Mapped[int] = mapped_column(Integer, nullable=False)
    paper: Mapped[Paper] = relationship(back_populates="authorships")
    author: Mapped[Author] = relationship(lazy="joined")


class LibraryItem(Base):
    __tablename__ = "library_items"
    __table_args__ = (Index("ix_library_user_status", "user_id", "status"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[ReadingStatus] = mapped_column(
        pg_enum(ReadingStatus, "reading_status"),
        nullable=False,
        server_default=ReadingStatus.to_read.value,
    )
    is_important: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (Index("uq_tags_user_name", "user_id", text("lower(name)"), unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)


class PaperTag(Base):
    __tablename__ = "paper_tags"

    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)


class Collection(Base, TimestampMixin):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class CollectionPaper(Base):
    __tablename__ = "collection_papers"

    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProjectStatus] = mapped_column(
        pg_enum(ProjectStatus, "project_status"),
        nullable=False,
        server_default=ProjectStatus.active.value,
    )


class ProjectPaper(Base):
    __tablename__ = "project_papers"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ResearchQuestion(Base, TimestampMixin):
    __tablename__ = "research_questions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[QuestionStatus] = mapped_column(
        pg_enum(QuestionStatus, "question_status"),
        nullable=False,
        server_default=QuestionStatus.draft.value,
    )


class QuestionPaper(Base):
    __tablename__ = "question_papers"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_questions.id", ondelete="CASCADE"), primary_key=True
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True)


class QuestionConcept(Base):
    __tablename__ = "question_concepts"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_questions.id", ondelete="CASCADE"), primary_key=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True)


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    paper_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("papers.id", ondelete="SET NULL"), index=True)
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_questions.id", ondelete="SET NULL"), index=True
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        pg_enum(TaskStatus, "task_status"), nullable=False, server_default=TaskStatus.todo.value
    )
    priority: Mapped[TaskPriority] = mapped_column(
        pg_enum(TaskPriority, "task_priority"), nullable=False, server_default=TaskPriority.medium.value
    )
    deadline: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Concept(Base, TimestampMixin):
    __tablename__ = "concepts"
    __table_args__ = (
        Index("uq_concepts_user_name", "user_id", text("lower(name)"), unique=True),
        Index(
            "uq_concepts_external",
            "user_id",
            "source",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[ConceptSource] = mapped_column(
        pg_enum(ConceptSource, "concept_source"), nullable=False, server_default=ConceptSource.user.value
    )
    external_id: Mapped[str | None] = mapped_column(String(120))


class PaperConcept(Base):
    __tablename__ = "paper_concepts"

    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True)
    relationship_type: Mapped[RelationshipType] = mapped_column(
        pg_enum(RelationshipType, "relationship_type"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class Note(Base, TimestampMixin):
    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_search", "search_vector", postgresql_using="gin"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    paper_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("papers.id", ondelete="SET NULL"), index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    highlight_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("highlights.id", ondelete="SET NULL"), index=True)
    page: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(content, ''))", persisted=True),
        nullable=False,
    )


class NoteConcept(Base):
    __tablename__ = "note_concepts"

    note_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True)


class NoteQuestion(Base):
    __tablename__ = "note_questions"

    note_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_questions.id", ondelete="CASCADE"), primary_key=True
    )


class NoteLink(Base):
    __tablename__ = "note_links"

    note_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    related_note_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)


class Highlight(Base):
    __tablename__ = "highlights"
    __table_args__ = (Index("ix_highlights_search", "search_vector", postgresql_using="gin"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_text: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    position_data: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(selected_text, '') || ' ' || coalesce(comment, ''))",
            persisted=True,
        ),
        nullable=False,
    )


class HighlightConcept(Base):
    __tablename__ = "highlight_concepts"

    highlight_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("highlights.id", ondelete="CASCADE"), primary_key=True)
    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True)


class HighlightQuestion(Base):
    __tablename__ = "highlight_questions"

    highlight_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("highlights.id", ondelete="CASCADE"), primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_questions.id", ondelete="CASCADE"), primary_key=True
    )


class Citation(Base):
    __tablename__ = "citations"
    __table_args__ = (CheckConstraint("citing_paper_id <> cited_paper_id", name="not_self"),)

    citing_paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True)
    cited_paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True)


class PaperFile(Base):
    __tablename__ = "paper_files"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), unique=True)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        pg_enum(ProcessingStatus, "processing_status"),
        nullable=False,
        server_default=ProcessingStatus.pending.value,
    )
    processing_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PaperEmbedding(Base):
    __tablename__ = "paper_embeddings"
    __table_args__ = (
        Index(
            "ix_paper_embeddings_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(VECTOR_DIM), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PaperChunk(Base):
    __tablename__ = "paper_chunks"
    __table_args__ = (
        Index("ix_paper_chunks_paper", "paper_id"),
        Index(
            "ix_paper_chunks_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(VECTOR_DIM), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)


class NoteEmbedding(Base):
    __tablename__ = "note_embeddings"

    note_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(VECTOR_DIM), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)


class HighlightEmbedding(Base):
    __tablename__ = "highlight_embeddings"

    highlight_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("highlights.id", ondelete="CASCADE"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(VECTOR_DIM), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)


class ProfileEmbedding(Base):
    __tablename__ = "profile_embeddings"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(VECTOR_DIM), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)


class ProjectEmbedding(Base):
    __tablename__ = "project_embeddings"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(VECTOR_DIM), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)


class ConceptEmbedding(Base):
    __tablename__ = "concept_embeddings"

    concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(VECTOR_DIM), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    __table_args__ = (Index("ix_activity_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    event_type: Mapped[ActivityType] = mapped_column(pg_enum(ActivityType, "activity_type"), nullable=False)
    paper_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("papers.id", ondelete="SET NULL"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
