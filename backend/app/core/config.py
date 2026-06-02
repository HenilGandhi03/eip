from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # DuckDB for MVP — swap DATABASE_URL to postgresql+asyncpg://... for prod
    DATABASE_URL: str = "data/processed/eip.duckdb"

    # GDELT source URLs
    GDELT_BASE_URL: str     = "http://data.gdeltproject.org/events"
    GDELT_GKG_BASE_URL: str = "http://data.gdeltproject.org/gkg"
    GDELT_INDEX_URL: str    = "http://data.gdeltproject.org/events/index.html"
    DATA_RAW_DIR: str       = "data/raw"
    DATA_PROCESSED_DIR: str = "data/processed"

    # Processing limits
    BATCH_SIZE: int         = 5_000
    MAX_EVENTS_PER_DAY: int = 100_000

    # Optional AI (Claude) for summarization only — never for causal inference
    ANTHROPIC_API_KEY: str  = ""

    # CAMEO 3-letter country codes to focus on
    # IND = India.  Add more: ["IND", "PAK", "CHN", "USA"]
    FOCUS_COUNTRIES: List[str] = ["IND"]

    class Config:
        env_file = ".env"


settings = Settings()
