from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./pragati.db"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret-change-me"
    jwt_alg: str = "HS256"
    jwt_expire_min: int = 60
    max_upload_mb: int = 25

    ocr_provider: str = "tesseract"
    extractor: str = "heuristic"
    storage_backend: str = "local"
    storage_root: str = "./data"

    confidence_ok: float = 0.75
    confidence_partial: float = 0.45

    openai_api_key: str | None = None
    azure_di_endpoint: str | None = None
    azure_di_key: str | None = None

    celery_task_always_eager: int = 0
    env: str = "dev"


settings = Settings()
