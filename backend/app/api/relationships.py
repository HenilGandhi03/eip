from fastapi import APIRouter, Query
from app.core.database import get_conn

router = APIRouter()


@router.get("/graph")
def get_relationship_graph(
    limit_nodes: int = Query(50, le=200),
    limit_edges: int = Query(100, le=500),
    min_confidence: float = Query(0.4, ge=0.0, le=1.0),
):
    """
    Graph data for visualization.
    Returns nodes (entities/events) and edges (observable relationships).
    All edges include explainability metadata.
    """
    conn = get_conn()

    # Top entities by frequency
    entity_rows = conn.execute("""
        SELECT id, canonical_name, entity_type, frequency
        FROM entities
        ORDER BY frequency DESC
        LIMIT ?
    """, [limit_nodes]).fetchall()

    nodes = [
        {"id": r[0], "label": r[1], "type": r[2], "weight": r[3], "node_type": "entity"}
        for r in entity_rows
    ]
    entity_ids = {r[0] for r in entity_rows}

    # Relationships between those entities
    rel_rows = conn.execute(f"""
        SELECT entity_a, entity_b, rel_type, evidence_count, confidence, explanation
        FROM relationships
        WHERE entity_a IN ({','.join('?' for _ in entity_ids)})
          AND entity_b IN ({','.join('?' for _ in entity_ids)})
          AND confidence >= ?
        ORDER BY confidence DESC
        LIMIT ?
    """, [*entity_ids, *entity_ids, min_confidence, limit_edges]).fetchall()

    edges = [
        {
            "source": r[0],
            "target": r[1],
            "type": r[2],
            "evidence": r[3],
            "confidence": r[4],
            "explanation": r[5],
            # Transparency: always separate facts from correlations
            "is_causal": False,
            "is_speculative": False,
        }
        for r in rel_rows
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "min_confidence": min_confidence,
            "note": "Edges represent observable co-occurrence patterns. No causal relationships are implied.",
        }
    }
