from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from datetime import date
from pydantic import BaseModel

from app.core.database import get_conn

router = APIRouter()


class EventOut(BaseModel):
    id: str
    date: str
    title: Optional[str]
    summary: Optional[str]
    category: Optional[str]
    goldstein: Optional[float]
    tone: Optional[float]
    country_a: Optional[str]
    country_b: Optional[str]
    location: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    num_mentions: Optional[int]
    num_sources: Optional[int]
    num_articles: Optional[int]
    source_url: Optional[str]


@router.get("/", response_model=list[EventOut])
def list_events(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    category: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    entity: Optional[str] = Query(None, description="Filter by entity name"),
    q: Optional[str] = Query(None, description="Full-text search"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
):
    """List events with filtering."""
    conn = get_conn()
    conditions = ["1=1"]
    params = []

    if start_date:
        conditions.append("date >= ?::DATE")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?::DATE")
        params.append(end_date)
    if category:
        conditions.append("category = ?")
        params.append(category.upper())
    if country:
        conditions.append("(country_a = ? OR country_b = ?)")
        params.extend([country.upper(), country.upper()])
    if q:
        conditions.append("(LOWER(title) LIKE ? OR LOWER(location) LIKE ?)")
        params.extend([f"%{q.lower()}%", f"%{q.lower()}%"])

    where = " AND ".join(conditions)
    sql = f"""
        SELECT id, CAST(date AS VARCHAR), title, summary, category, goldstein, tone,
               country_a, country_b, location, lat, lon,
               num_mentions, num_sources, num_articles, source_url
        FROM events
        WHERE {where}
        ORDER BY date DESC, num_mentions DESC
        LIMIT {limit} OFFSET {offset}
    """
    rows = conn.execute(sql, params).fetchall()
    cols = ["id","date","title","summary","category","goldstein","tone",
            "country_a","country_b","location","lat","lon",
            "num_mentions","num_sources","num_articles","source_url"]
    return [dict(zip(cols, r)) for r in rows]


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: str):
    """Get a single event by ID."""
    conn = get_conn()
    row = conn.execute("""
        SELECT id, CAST(date AS VARCHAR), title, summary, category, goldstein, tone,
               country_a, country_b, location, lat, lon,
               num_mentions, num_sources, num_articles, source_url
        FROM events WHERE id = ?
    """, [event_id]).fetchone()
    if not row:
        raise HTTPException(404, "Event not found")
    cols = ["id","date","title","summary","category","goldstein","tone",
            "country_a","country_b","location","lat","lon",
            "num_mentions","num_sources","num_articles","source_url"]
    return dict(zip(cols, row))


@router.get("/{event_id}/related")
def get_related_events(event_id: str, limit: int = 10):
    """Get events related to this one via observable relationships."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT
            er.rel_type,
            er.days_apart,
            er.confidence,
            er.explanation,
            e.id, CAST(e.date AS VARCHAR), e.title, e.category, e.location,
            e.num_sources, e.tone
        FROM event_relationships er
        JOIN events e ON (
            CASE WHEN er.event_a = ? THEN er.event_b ELSE er.event_a END = e.id
        )
        WHERE er.event_a = ? OR er.event_b = ?
        ORDER BY er.confidence DESC
        LIMIT ?
    """, [event_id, event_id, event_id, limit]).fetchall()

    return [
        {
            "relationship_type": r[0],
            "days_apart": r[1],
            "confidence": r[2],
            "explanation": r[3],
            "event": {
                "id": r[4], "date": r[5], "title": r[6],
                "category": r[7], "location": r[8],
                "num_sources": r[9], "tone": r[10],
            }
        }
        for r in rows
    ]


@router.get("/stats/summary")
def get_stats():
    """Summary statistics for the dashboard."""
    conn = get_conn()
    stats = conn.execute("""
        SELECT
            COUNT(*) as total_events,
            MIN(date) as earliest,
            MAX(date) as latest,
            COUNT(DISTINCT category) as categories,
            COUNT(DISTINCT country_a) as countries,
            SUM(num_mentions) as total_mentions
        FROM events
    """).fetchone()
    return {
        "total_events": stats[0],
        "date_range": {"from": str(stats[1]), "to": str(stats[2])},
        "categories": stats[3],
        "countries": stats[4],
        "total_mentions": stats[5],
    }
