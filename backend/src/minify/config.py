"""Central, env-driven configuration.

Single source of truth for anything that differs between local and cloud, or
between LLM providers (design.md's "config over code branching" principle):
DB connection, storage backend, LLM provider/model, CORS origins. Read via
`get_settings()`, never by constructing `Settings()` directly, so the whole
app shares one cached instance.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed view over `.env` (or real environment variables in the cloud)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "local"

    database_url: str = "sqlite:///./minify.db"

    storage_backend: str = "local_disk"
    storage_local_path: str = "./data/files"

    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    llm_api_key: str = ""

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
