export type User = {
  id: string;
  name: string;
  email: string;
  research_level: string | null;
  bio: string | null;
  profile: {
    research_interests: string[];
    skills: string[];
    preferred_topics: string[];
  };
};

export type Meta = {
  max_upload_bytes: number;
  research_levels: string[];
  reading_statuses: string[];
  question_statuses: string[];
  question_transitions: Record<string, string[]>;
  task_statuses: string[];
  task_priorities: string[];
  project_statuses: string[];
  relationship_types: string[];
  search_modes: string[];
  discovery_sources: string[];
};

export type Author = { id: string; name: string; affiliation: string | null };
export type Tag = { id: string; name: string };

export type Paper = {
  id: string;
  title: string;
  abstract: string | null;
  publication: string | null;
  year: number | null;
  doi: string | null;
  pdf_url: string | null;
  landing_url: string | null;
  external_citation_count: number | null;
  source: string;
  embedding_status: string;
  authors: Author[];
  tags: Tag[];
  in_library: boolean;
  status: string | null;
  is_important: boolean;
  is_favorite: boolean;
  has_file: boolean;
  concepts?: { id: string; name: string; relationship_type: string }[];
  collection_ids?: string[];
  project_ids?: string[];
  references_count?: number;
  cited_by_count?: number;
  notes_count?: number;
  highlights_count?: number;
  processing_status?: string | null;
  processing_error?: string | null;
};

export type Page<T> = { items: T[]; total: number; limit: number; offset: number };

export type Project = {
  id: string;
  name: string;
  description: string | null;
  status: string;
  progress: number;
  paper_count: number;
  note_count: number;
  concept_count: number;
  open_question_count: number;
  task_count: number;
};

export type Collection = {
  id: string;
  name: string;
  description: string | null;
  project_id: string | null;
  paper_count: number;
};

export type Question = {
  id: string;
  title: string;
  description: string | null;
  status: string;
  allowed_statuses: string[];
  project_id: string | null;
  paper_ids: string[];
  concept_ids: string[];
  note_count: number;
};

export type Task = {
  id: string;
  title: string;
  description: string | null;
  project_id: string | null;
  paper_id: string | null;
  question_id: string | null;
  status: string;
  priority: string;
  deadline: string | null;
  completed_at: string | null;
};

export type Concept = {
  id: string;
  name: string;
  description: string | null;
  source: string;
  paper_count: number;
  indexed: boolean;
};

export type Note = {
  id: string;
  content: string;
  paper_id: string | null;
  paper_title: string | null;
  project_id: string | null;
  highlight_id: string | null;
  page: number | null;
  concept_ids: string[];
  question_ids: string[];
  related_note_ids: string[];
  created_at: string;
};

export type Highlight = {
  id: string;
  paper_id: string;
  page: number;
  selected_text: string;
  comment: string | null;
  rects: { x: number; y: number; width: number; height: number }[];
  concept_ids: string[];
  question_ids: string[];
};

export type DiscoveryOut = {
  items: Discovered[];
  sources: { source: string; count: number; error?: string | null }[];
};

export type Discovered = {
  source: string;
  external_id: string;
  title: string;
  abstract: string | null;
  publication: string | null;
  year: number | null;
  authors: string[];
  topics: string[];
  citation_count: number | null;
  library_paper_id: string | null;
};

export type Overview = {
  papers_saved: number;
  papers_reading: number;
  papers_completed: number;
  notes: number;
  highlights: number;
  questions: number;
  concepts: number;
  projects: number;
  tasks_open: number;
  unfinished_papers: number;
  reading_streak_days: number;
  authors_encountered: number;
  reading_to_note_rate: number | null;
  question_status: Record<string, number>;
  top_tags: { name: string; count: number }[];
  monthly_activity: { month: string; papers_opened: number; papers_saved: number; notes_created: number }[];
  weekly_reading: { week: string; count: number }[];
  project_progress: { id: string; name: string; progress: number; papers: number; notes: number; concepts: number; open_questions: number }[];
  recent_events: { id: string; event_type: string; created_at: string }[];
};

export type Recommendation = {
  paper: Paper;
  score: number;
  components: Record<string, number>;
};

export type GraphNode = {
  id: string;
  type: string;
  label: string;
  community: number | null;
  pagerank: number | null;
  data: Record<string, unknown>;
};

export type GraphPayload = {
  nodes: GraphNode[];
  edges: { id: string; source: string; target: string; type: string }[];
  influential: { id: string; label: string; score: number }[];
};
