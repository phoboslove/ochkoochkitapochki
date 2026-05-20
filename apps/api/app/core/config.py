from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field("sqlite+aiosqlite:///./buchuchet.db")
    storage_dir: str = "./storage/local"
    storage_backend: str = "local"  # "local" | "s3"

    jwt_secret: str = "change-me"
    jwt_alg: str = "HS256"
    jwt_ttl_min: int = 60

    cors_origins: list[str] = ["http://localhost:3000"]

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    ai_default_model: str = "gpt-3.5-turbo"

    s3_endpoint: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_bucket: str = "buchuchet"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"

    ocr_provider: str = "mock"        # mock | azure | ocr_space
    azure_doc_intel_endpoint: str | None = None
    azure_doc_intel_key: str | None = None
    ocr_space_api_key: str | None = None
    ocr_space_language: str = "rus"   # eng|rus|kaz — OCR.Space allows one per call


@lru_cache
def _get_settings() -> Settings:
    return Settings()


settings = _get_settings()
