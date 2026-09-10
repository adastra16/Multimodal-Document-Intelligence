"""Environment-backed application settings. Secrets never live in code."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and optional .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    database_url: str = "sqlite:///./data/app.db"
    data_dir: Path = Path("./data")
    max_upload_mb: int = 50
    embedding_dimensions: int = 256
    retrieval_semantic_weight: float = 0.65
    retrieval_lexical_weight: float = 0.35
    retrieval_candidate_multiplier: int = 4
    retrieval_rerank_seed_limit: int = 3
    retrieval_expansion_per_seed: int = 3
    generation_min_evidence_score: float = 0.15

    ocr_command: str = "tesseract"
    ocr_language: str = "eng"
    ocr_dpi: int = 220

    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = ""
    llm_model: str = "llama3.1"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in {"development", "dev", "local"}

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
