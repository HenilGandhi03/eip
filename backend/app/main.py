"""
Event Intelligence Platform — FastAPI Backend
GDELT-powered event intelligence with entity relationship mapping.
"""
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.api import events, entities, relationships, ingest
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Event Intelligence Platform...")
    # On startup, ensure DB is initialized
    from app.core.database import init_db
    await init_db()
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="Event Intelligence Platform",
    description="GDELT-powered contextual intelligence for world events",
    version="1.0.0",
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
app.include_router(ingest.router,        prefix="/api/ingest",         tags=["Data Ingestion"])


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
