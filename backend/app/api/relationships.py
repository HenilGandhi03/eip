from fastapi import APIRouter, Query
from app.core.database import get_conn

router = APIRouter()


@router.get("/graph")
def get_relationship_graph(
    limit_nodes:    int   = Query(60,  le=200),
    limit_edges:    int   = Query(150, le=600),
    min_confidence: float = Query(0.4, ge=0.0, le=1.0),
):
    """
    Graph payload for D3/Cytoscape visualization.
    Nodes = entities. Edges = weighted observable co-occurrence.
    Every edge carries a full signal breakdown for transparency.
    """
    conn = get_conn()

    entity_rows = conn.execute("""
        SELECT id, canonical_name, entity_type, frequency
        FROM entities
        ORDER BY frequency DESC
        LIMIT ?
    """, [limit_nodes]).fetchall()

    if not entity_rows:
        return {
            "nodes": [],
            "edges": [],
            "metadata": {
                "min_confidence": min_confidence,
                "total_nodes": 0,
                "total_edges": 0,
                "note": "No entities yet. POST /api/ingest/seed to load sample data.",
            },
        }

    nodes = [
        {
            "id":     r[0],
            "label":  r[1],
            "type":   r[2] or "unknown",
            "weight": r[3] or 0,
        }
        for r in entity_rows
    ]

    entity_ids   = [r[0] for r in entity_rows]
    placeholders = ", ".join("?" for _ in entity_ids)

    rel_rows = conn.execute(f"""
        SELECT
            entity_a, entity_b,
            rel_type,
            evidence_count,
            co_mention_count,
            confidence,
            explanation
        FROM relationships
        WHERE entity_a IN ({placeholders})
          AND entity_b IN ({placeholders})
          AND confidence >= ?
        ORDER BY confidence DESC
        LIMIT ?
    """, [*entity_ids, *entity_ids, min_confidence, limit_edges]).fetchall()

    edges = [
        {
            "source":          r[0],
            "target":          r[1],
            "type":            r[2],
            "evidence":        r[3],
            "co_mention_count": r[4],
            "confidence":      round(r[5], 3) if r[5] else 0,
            "explanation":     r[6],
            "is_causal":       False,
            "is_speculative":  False,
        }
        for r in rel_rows
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "min_confidence": min_confidence,
            "total_nodes":    len(nodes),
            "total_edges":    len(edges),
            "note": (
                "Edges are observable co-occurrence signals only. "
                "Confidence is a weighted composite (location + country + category + "
                "temporal proximity + mention volume). "
                "No causal relationships are implied."
            ),
        },
    }
