from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from app.core.database import get_conn

router = APIRouter()


@router.get("/")
def list_entities(
    entity_type: Optional[str] = Query(None),
    q:           Optional[str] = Query(None),
    limit:       int           = Query(50, le=200),
):
    conn = get_conn()
    conditions, params = ["1=1"], []

    if entity_type:
        conditions.append("entity_type = ?")
        params.append(entity_type)
    if q:
        conditions.append("LOWER(canonical_name) LIKE ?")
        params.append(f"%{q.lower()}%")

    rows = conn.execute(f"""
        SELECT id, canonical_name, aliases, entity_type, frequency,
               CAST(first_seen AS VARCHAR), CAST(last_seen AS VARCHAR)
        FROM entities
        WHERE {" AND ".join(conditions)}
        ORDER BY frequency DESC
        LIMIT {limit}
    """, params).fetchall()

    return [
        {
            "id":         r[0],
            "name":       r[1],
            "aliases":    r[2] or [],
            "type":       r[3] or "unknown",
            "frequency":  r[4] or 0,
            "first_seen": r[5],
            "last_seen":  r[6],
        }
        for r in rows
    ]


@router.get("/{entity_id}")
def get_entity(entity_id: str):
    conn = get_conn()
    row = conn.execute("""
        SELECT id, canonical_name, aliases, entity_type, frequency,
               CAST(first_seen AS VARCHAR), CAST(last_seen AS VARCHAR)
        FROM entities WHERE id = ?
    """, [entity_id]).fetchone()
    if not row:
        raise HTTPException(404, "Entity not found")
    return {
        "id": row[0], "name": row[1], "aliases": row[2] or [],
        "type": row[3], "frequency": row[4],
        "first_seen": row[5], "last_seen": row[6],
    }


@router.get("/{entity_id}/events")
def entity_events(entity_id: str, limit: int = Query(50, le=200)):
    conn = get_conn()
    rows = conn.execute("""
        SELECT e.id, CAST(e.date AS VARCHAR), e.title, e.category,
               e.location, e.tone, e.num_sources
        FROM events e
        JOIN event_entities ee ON e.id = ee.event_id
        WHERE ee.entity_id = ?
        ORDER BY e.date DESC
        LIMIT ?
    """, [entity_id, limit]).fetchall()

    return [
        {"id": r[0], "date": r[1], "title": r[2], "category": r[3],
         "location": r[4], "tone": r[5], "sources": r[6]}
        for r in rows
    ]


@router.get("/{entity_id}/relationships")
def entity_relationships(entity_id: str):
    """
    Observable relationships for an entity.
    Includes weighted confidence breakdown + full explainability.
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT
            r.rel_type,
            r.evidence_count,
            r.co_mention_count,
            r.confidence,
            r.explanation,
            CAST(r.first_seen AS VARCHAR),
            CAST(r.last_seen  AS VARCHAR),
            e.id, e.canonical_name, e.entity_type
        FROM relationships r
        JOIN entities e
          ON CASE WHEN r.entity_a = ? THEN r.entity_b ELSE r.entity_a END = e.id
        WHERE r.entity_a = ? OR r.entity_b = ?
        ORDER BY r.confidence DESC, r.evidence_count DESC
        LIMIT 50
    """, [entity_id, entity_id, entity_id]).fetchall()

    return [
        {
            "type":           r[0],
            "evidence_count": r[1],
            "co_mention_count": r[2],
            "confidence":     round(r[3], 3) if r[3] else 0,
            "explanation":    r[4],
            "first_seen":     r[5],
            "last_seen":      r[6],
            "entity":         {"id": r[7], "name": r[8], "type": r[9]},
            "transparency": {
                "is_causal":      False,
                "is_speculative": False,
                "basis": "Weighted co-occurrence signals from GDELT data. "
                         "Confidence = combination of frequency, mention volume, "
                         "and temporal proximity. No causal claims.",
            },
        }
        for r in rows
    ]
