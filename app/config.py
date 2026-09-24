from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Shortlist"
    app_version: str = "1.0.0"

    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'shortlist.db'}"
    upload_dir: Path = BASE_DIR / "data" / "uploads"
    log_dir: Path = BASE_DIR / "logs"
    log_level: str = "INFO"
    max_upload_mb: int = 10
    seed_demo_data: bool = False
    sample_data_dir: Path = BASE_DIR / "sample_data"

    ocr_enabled: bool = True

    embedding_backend: str = "hashing"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "recruiting@example.com"
    smtp_use_tls: bool = True

    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-5"


@lru_cache
def get_settings() -> Settings:
    return Settings()

