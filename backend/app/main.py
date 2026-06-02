"""
Event Intelligence Platform — FastAPI Backend
GDELT-powered event intelligence with entity relationship mapping.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.api import events, entities, relationships, ingest
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Event Intelligence Platform...")
    from app.core.database import init_db
    await init_db()
    logger.info("DB ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Event Intelligence Platform",
    description="GDELT-powered contextual intelligence for world events",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router,        prefix="/api/events",        tags=["Events"])
app.include_router(entities.router,      prefix="/api/entities",      tags=["Entities"])
app.include_router(relationships.router, prefix="/api/relationships",  tags=["Relationships"])
app.include_router(ingest.router,        prefix="/api/ingest",         tags=["Ingestion"])


@app.get("/health")
def health():
    from app.core.database import get_conn
    try:
        count = get_conn().execute("SELECT COUNT(*) FROM events").fetchone()[0]
        return {"status": "ok", "version": "2.0.0", "events_in_db": count}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
