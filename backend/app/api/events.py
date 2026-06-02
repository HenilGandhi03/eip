from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from pydantic import BaseModel
from app.core.database import get_conn

router = APIRouter()


class EventOut(BaseModel):
    id: str
    date: str
    title: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None
    goldstein: Optional[float] = None
    tone: Optional[float] = None
    country_a: Optional[str] = None
    country_b: Optional[str] = None
    location: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    num_mentions: Optional[int] = None
    num_sources: Optional[int] = None
    num_articles: Optional[int] = None
    source_url: Optional[str] = None


_COLS = ["id","date","title","summary","category","goldstein","tone",
         "country_a","country_b","location","lat","lon",
         "num_mentions","num_sources","num_articles","source_url"]


# ── /stats/summary MUST come BEFORE /{event_id} ──────────────────────────────

@router.get("/stats/summary")
def get_stats():
    """Dashboard statistics. Safe even on empty DB."""
    conn = get_conn()
    row = conn.execute("""
        SELECT
            COUNT(*)                       AS total_events,
            MIN(date)                      AS earliest,
            MAX(date)                      AS latest,
            COUNT(DISTINCT category)       AS categories,
            COUNT(DISTINCT country_a)      AS countries,
            COALESCE(SUM(num_mentions), 0) AS total_mentions
        FROM events
    """).fetchone()

    if not row or row[0] == 0:
        return {
            "total_events":   0,
            "date_range":     {"from": None, "to": None},
            "categories":     0,
            "countries":      0,
            "total_mentions": 0,
            "tip": "No events in DB yet. Use POST /api/ingest/seed for sample data, or POST /api/ingest/trigger for live GDELT data.",
        }

    return {
        "total_events":   row[0],
        "date_range":     {"from": str(row[1]) if row[1] else None,
                           "to":   str(row[2]) if row[2] else None},
        "categories":     row[3],
        "countries":      row[4],
        "total_mentions": row[5],
    }


# ── List events ───────────────────────────────────────────────────────────────

@router.get("/", response_model=list[EventOut])
def list_events(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date:   Optional[str] = Query(None, description="YYYY-MM-DD"),
    category:   Optional[str] = Query(None),
    country:    Optional[str] = Query(None),
    q:          Optional[str] = Query(None, description="Search title / location"),
    limit:  int = Query(200, le=1000),
    offset: int = Query(0),
):
    conn = get_conn()
    conditions, params = ["1=1"], []

    if start_date:
        conditions.append("date >= CAST(? AS DATE)")
        params.append(start_date)
    if end_date:
        conditions.append("date <= CAST(? AS DATE)")
        params.append(end_date)
    if category:
        conditions.append("category = ?")
        params.append(category.upper())
    if country:
        conditions.append("(country_a = ? OR country_b = ?)")
        params += [country.upper(), country.upper()]
    if q:
        conditions.append(
            "(LOWER(COALESCE(title,'')) LIKE ? OR LOWER(COALESCE(location,'')) LIKE ?)"
        )
        params += [f"%{q.lower()}%", f"%{q.lower()}%"]

    sql = f"""
        SELECT id, CAST(date AS VARCHAR), title, summary, category, goldstein, tone,
               country_a, country_b, location, lat, lon,
               num_mentions, num_sources, num_articles, source_url
        FROM events
        WHERE {" AND ".join(conditions)}
        ORDER BY date DESC, COALESCE(num_mentions, 0) DESC
        LIMIT {limit} OFFSET {offset}
    """
    rows = conn.execute(sql, params).fetchall()
    return [dict(zip(_COLS, r)) for r in rows]


# ── Related events ────────────────────────────────────────────────────────────
# MUST come before /{event_id} — otherwise "related" is treated as an event ID

@router.get("/{event_id}/related")
def get_related(event_id: str, limit: int = Query(10, le=50)):
    """
    Related events with weighted confidence scores and full explanation.
    Only observable co-occurrence relationships — no causal claims.
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT
            er.rel_type,
            er.days_apart,
            er.confidence,
            er.score_co_location,
            er.score_co_country,
            er.score_co_category,
            er.score_temporal,
            er.score_mention_vol,
            er.explanation,
            e.id, CAST(e.date AS VARCHAR), e.title,
            e.category, e.location, e.num_sources, e.tone
        FROM event_relationships er
        JOIN events e
          ON CASE WHEN er.event_a = ? THEN er.event_b ELSE er.event_a END = e.id
        WHERE (er.event_a = ? OR er.event_b = ?)
        ORDER BY er.confidence DESC
        LIMIT ?
    """, [event_id, event_id, event_id, limit]).fetchall()

    return [
        {
            "relationship_type": r[0],
            "days_apart":        r[1],
            "confidence":        round(r[2], 3) if r[2] else 0,
            "signal_breakdown": {
                "co_location": round(r[3], 3) if r[3] else 0,
                "co_country":  round(r[4], 3) if r[4] else 0,
                "co_category": round(r[5], 3) if r[5] else 0,
                "temporal":    round(r[6], 3) if r[6] else 0,
                "mention_vol": round(r[7], 3) if r[7] else 0,
            },
            "explanation": r[8],
            "is_causal":      False,
            "is_speculative": False,
            "event": {
                "id":       r[9],  "date":     r[10], "title":    r[11],
                "category": r[12], "location": r[13],
                "num_sources": r[14], "tone":  r[15],
            },
        }
        for r in rows
    ]


# ── Single event — MUST be last ───────────────────────────────────────────────

@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: str):
    conn = get_conn()
    row = conn.execute("""
        SELECT id, CAST(date AS VARCHAR), title, summary, category, goldstein, tone,
               country_a, country_b, location, lat, lon,
               num_mentions, num_sources, num_articles, source_url
        FROM events WHERE id = ?
    """, [event_id]).fetchone()
    if not row:
        raise HTTPException(404, "Event not found")
    return dict(zip(_COLS, row))
