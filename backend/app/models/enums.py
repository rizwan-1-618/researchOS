from __future__ import annotations

from enum import Enum


class ResearchLevel(str, Enum):
    undergraduate = "undergraduate"
    masters = "masters"
    doctoral = "doctoral"
    postdoctoral = "postdoctoral"
    professional = "professional"


class ReadingStatus(str, Enum):
    to_read = "to_read"
    reading = "reading"
    completed = "completed"


class ProjectStatus(str, Enum):
    active = "active"
    paused = "paused"
    completed = "completed"


class QuestionStatus(str, Enum):
    draft = "draft"
    investigating = "investigating"
    supported = "supported"
    unsupported = "unsupported"
    open = "open"
    completed = "completed"


class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class ProfileTermKind(str, Enum):
    interest = "interest"
    skill = "skill"
    topic = "topic"


class ConceptSource(str, Enum):
    user = "user"
    openalex = "openalex"
    semantic_scholar = "semantic_scholar"
    arxiv = "arxiv"
    crossref = "crossref"


class RelationshipType(str, Enum):
    about = "about"
    uses_method = "uses_method"
    uses_dataset = "uses_dataset"
    related_to = "related_to"


class EmbeddingStatus(str, Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class ProcessingStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class PaperSource(str, Enum):
    manual = "manual"
    upload = "upload"
    openalex = "openalex"
    semantic_scholar = "semantic_scholar"
    arxiv = "arxiv"
    crossref = "crossref"
    citation = "citation"


class ActivityType(str, Enum):
    paper_opened = "paper_opened"
    paper_saved = "paper_saved"
    paper_completed = "paper_completed"
    note_created = "note_created"
    highlight_created = "highlight_created"
    question_created = "question_created"
    task_completed = "task_completed"
    project_updated = "project_updated"


class SearchMode(str, Enum):
    keyword = "keyword"
    semantic = "semantic"
    hybrid = "hybrid"


class DiscoverySource(str, Enum):
    all = "all"
    openalex = "openalex"
    semantic_scholar = "semantic_scholar"
    arxiv = "arxiv"
