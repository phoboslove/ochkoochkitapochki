from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field("sqlite+aiosqlite:///./buchuchet.db")
    storage_dir: str = "./storage/local"
    storage_backend: str = "local"  # "local" | "s3"

    # Environment & gating
    # `app_env` controls dev-only behavior (demo seeding, default credentials).
    # Set to "production" (or any value other than "dev"/"development") on real
    # deploys to suppress the demo company/owner. Production demo seed is a
    # known credentialed account in the repo — must NOT exist on public servers.
    app_env: str = "dev"
    enable_demo_seed: bool = True   # auto-disabled when app_env=production

    jwt_secret: str = "change-me"
    jwt_alg: str = "HS256"
    jwt_ttl_min: int = 60

    cors_origins: list[str] = ["http://localhost:3000"]

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    ai_default_model: str = "gpt-3.5-turbo"

    s3_endpoint: str = "http://localhost:9000"
    # Public-facing endpoint for presigned URLs, if it differs from
    # s3_endpoint (e.g. api talks to MinIO over the internal Docker network
    # at http://minio:9000, but presigned links handed to browsers need a
    # publicly resolvable host). SigV4 signs the `host` header, so presigned
    # URLs must be generated against whichever host will actually receive
    # the request — falls back to s3_endpoint when unset.
    s3_public_endpoint: str | None = None
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
    s = Settings()
    # Hard rule: production environments NEVER ship the demo seed. We toggle
    # the explicit flag here so a single env var (APP_ENV=production) is
    # enough to lock down credentials.
    if s.app_env.lower() in ("production", "prod"):
        s.enable_demo_seed = False
    return s


settings = _get_settings()
