from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Database — uses DuckDB for MVP (swap to PostgreSQL for production)
    DATABASE_URL: str = "data/processed/eip.duckdb"

    # GDELT
    GDELT_BASE_URL: str = "http://data.gdeltproject.org/events"
    GDELT_GKG_BASE_URL: str = "http://data.gdeltproject.org/gkg"
    GDELT_INDEX_URL: str = "http://data.gdeltproject.org/events/index.html"
    DATA_RAW_DIR: str = "data/raw"
    DATA_PROCESSED_DIR: str = "data/processed"

    # Processing
    BATCH_SIZE: int = 10_000
    MAX_EVENTS_PER_DAY: int = 50_000

    # AI (optional — for summarization / entity extraction)
    ANTHROPIC_API_KEY: str = ""

    # Focus regions for MVP (CAMEO country codes)
    FOCUS_COUNTRIES: List[str] = ["IND"]  # India focus for MVP

    class Config:
        env_file = ".env"


settings = Settings()
