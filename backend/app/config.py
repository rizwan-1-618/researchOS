from __future__ import annotations

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT / ".env", BACKEND / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    database_url_sync: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:3000"
    trust_proxy: bool = False

    storage_backend: str = "local"
    storage_local_path: str = "storage"
    s3_endpoint: str = ""
    s3_bucket: str = "papers"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"

    contact_email: str = ""
    semantic_scholar_api_key: str = ""
    openalex_base: str = "https://api.openalex.org"
    semantic_scholar_base: str = "https://api.semanticscholar.org/graph/v1"
    arxiv_base: str = "https://export.arxiv.org/api/query"
    crossref_base: str = "https://api.crossref.org"
    http_timeout_seconds: float = 20
    retry_after_default_seconds: float = 1
    retry_after_cap_seconds: float = 5
    discovery_page_size: int = 10
    discovery_max_page_size: int = 25
    discovery_source_priority: str = "openalex,semantic_scholar,arxiv"
    citation_fetch_limit: int = 12
    citation_batch_size: int = 20

    embedding_provider: str = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384
    embedding_api_base: str = ""
    embedding_api_key: str = ""
    embedding_api_model: str = ""
    embedding_input_characters: int = 2000
    chunk_size: int = 1200
    chunk_overlap: int = 150

    max_upload_bytes: int = 25 * 1024 * 1024
    pdf_download_max_bytes: int = 25 * 1024 * 1024
    pdf_redirect_limit: int = 3
    pdf_signature: str = "%PDF"
    allowed_pdf_content_types: str = "application/pdf,application/octet-stream,application/x-pdf"
    pdf_job_timeout_seconds: int = 300

    auth_rate_limit: int = 10
    auth_rate_window_seconds: int = 60
    api_default_page_size: int = 20
    api_max_page_size: int = 100

    recommendation_limit: int = 12
    recommendation_candidate_pool: int = 40
    recommendation_min_candidates: int = 8
    recommendation_discovery_limit: int = 10
    recommendation_cache_ttl_seconds: int = 300
    recommendation_weight_semantic: float = 0.30
    recommendation_weight_topic: float = 0.15
    recommendation_weight_interest: float = 0.25
    recommendation_weight_project: float = 0.15
    recommendation_weight_history: float = 0.15

    project_progress_task_weight: float = 0.5
    project_progress_paper_weight: float = 0.5
    search_limit: int = 20
    search_pool: int = 50
    rank_fusion_k: int = 60
    graph_neighbor_limit: int = 40
    graph_paper_limit: int = 200
    graph_seed: int = 0
    analytics_months: int = 12
    analytics_weeks: int = 12
    analytics_top_tags: int = 8
    analytics_recent_events: int = 12
    influential_limit: int = 8
    queue_name: str = "researchos"

    @model_validator(mode="after")
    def validate_settings(self):
        recommendation_total = (
            self.recommendation_weight_semantic
            + self.recommendation_weight_topic
            + self.recommendation_weight_interest
            + self.recommendation_weight_project
            + self.recommendation_weight_history
        )
        if abs(recommendation_total - 1) > 0.001:
            raise ValueError("recommendation weights must sum to 1")
        progress_total = self.project_progress_task_weight + self.project_progress_paper_weight
        if abs(progress_total - 1) > 0.001:
            raise ValueError("project progress weights must sum to 1")
        if self.embedding_provider not in {"fastembed", "openai", "fake"}:
            raise ValueError("EMBEDDING_PROVIDER must be fastembed, openai, or fake")
        if self.embedding_provider == "openai" and not (
            self.embedding_api_base and self.embedding_api_key and self.embedding_api_model
        ):
            raise ValueError(
                "openai embeddings require EMBEDDING_API_BASE, EMBEDDING_API_KEY, and EMBEDDING_API_MODEL"
            )
        if self.storage_backend not in {"local", "s3"}:
            raise ValueError("STORAGE_BACKEND must be local or s3")
        if self.storage_backend == "s3" and not (
            self.s3_endpoint and self.s3_bucket and self.s3_access_key and self.s3_secret_key
        ):
            raise ValueError("s3 storage requires endpoint, bucket, access key, and secret key")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk overlap must be smaller than chunk size")
        return self

    @property
    def storage_path(self) -> Path:
        path = Path(self.storage_local_path)
        if not path.is_absolute():
            path = BACKEND / path
        return path

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_pdf_types(self) -> set[str]:
        return {item.strip().lower() for item in self.allowed_pdf_content_types.split(",") if item.strip()}

    @property
    def discovery_priority(self) -> list[str]:
        return [item.strip() for item in self.discovery_source_priority.split(",") if item.strip()]


settings = Settings()
