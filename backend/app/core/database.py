"""
DuckDB database layer.
IMPORTANT: DuckDB uses ON CONFLICT DO NOTHING, NOT "INSERT OR IGNORE".
For production swap to PostgreSQL + asyncpg. Neo4j for graph queries.
"""
import duckdb
import os
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

_conn: duckdb.DuckDBPyConnection | None = None


def get_conn() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        os.makedirs(settings.DATA_PROCESSED_DIR, exist_ok=True)
        _conn = duckdb.connect(settings.DATABASE_URL)
    return _conn


async def init_db():
    conn = get_conn()
    logger.info("Initialising DuckDB schema…")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id            VARCHAR PRIMARY KEY,
            date          DATE NOT NULL,
            year          INTEGER,
            month         INTEGER,
            day           INTEGER,
            title         VARCHAR,
            summary       VARCHAR,
            category      VARCHAR,
            cameo_code    VARCHAR,
            goldstein     DOUBLE,
            tone          DOUBLE,
            country_a     VARCHAR,
            country_b     VARCHAR,
            location      VARCHAR,
            lat           DOUBLE,
            lon           DOUBLE,
            num_mentions  INTEGER DEFAULT 0,
            num_sources   INTEGER DEFAULT 0,
            num_articles  INTEGER DEFAULT 0,
            source_url    VARCHAR,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id             VARCHAR PRIMARY KEY,
            canonical_name VARCHAR NOT NULL,
            aliases        VARCHAR[],
            entity_type    VARCHAR,
            country        VARCHAR,
            frequency      INTEGER DEFAULT 0,
            first_seen     DATE,
            last_seen      DATE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_entities (
            event_id  VARCHAR REFERENCES events(id),
            entity_id VARCHAR REFERENCES entities(id),
            role      VARCHAR,
            PRIMARY KEY (event_id, entity_id, role)
        )
    """)

    # Weighted relationship table
    # confidence_score = weighted combination of all signals (see relationship_builder.py)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS relationships (
            id             VARCHAR PRIMARY KEY,
            entity_a       VARCHAR REFERENCES entities(id),
            entity_b       VARCHAR REFERENCES entities(id),
            rel_type       VARCHAR NOT NULL,
            evidence_count INTEGER DEFAULT 0,
            -- Raw signal counts
            co_mention_count   INTEGER DEFAULT 0,
            co_location_count  INTEGER DEFAULT 0,
            co_topic_count     INTEGER DEFAULT 0,
            temporal_count     INTEGER DEFAULT 0,
            -- Weighted composite score (0.0–1.0)
            confidence         DOUBLE DEFAULT 0.0,
            explanation        VARCHAR,
            first_seen         DATE,
            last_seen          DATE,
            UNIQUE(entity_a, entity_b, rel_type)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_relationships (
            event_a         VARCHAR REFERENCES events(id),
            event_b         VARCHAR REFERENCES events(id),
            rel_type        VARCHAR NOT NULL,
            shared_entities VARCHAR[],
            shared_themes   VARCHAR[],
            days_apart      INTEGER,
            -- Weighted score components stored for transparency
            score_co_location  DOUBLE DEFAULT 0.0,
            score_co_country   DOUBLE DEFAULT 0.0,
            score_co_category  DOUBLE DEFAULT 0.0,
            score_temporal     DOUBLE DEFAULT 0.0,
            score_mention_vol  DOUBLE DEFAULT 0.0,
            confidence         DOUBLE DEFAULT 0.0,
            explanation        VARCHAR,
            PRIMARY KEY (event_a, event_b, rel_type)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS gkg_records (
            id               VARCHAR PRIMARY KEY,
            date             DATE,
            source_url       VARCHAR,
            themes           VARCHAR[],
            locations        VARCHAR[],
            persons          VARCHAR[],
            organizations    VARCHAR[],
            tone             DOUBLE,
            positive_score   DOUBLE,
            negative_score   DOUBLE,
            polarity         DOUBLE,
            activity_density DOUBLE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_log (
            id                VARCHAR PRIMARY KEY,
            file_date         DATE,
            file_url          VARCHAR,
            status            VARCHAR,
            records_processed INTEGER DEFAULT 0,
            error_msg         VARCHAR,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Indexes
    for ddl in [
        "CREATE INDEX IF NOT EXISTS idx_events_date     ON events(date)",
        "CREATE INDEX IF NOT EXISTS idx_events_country  ON events(country_a)",
        "CREATE INDEX IF NOT EXISTS idx_events_category ON events(category)",
        "CREATE INDEX IF NOT EXISTS idx_ee_entity       ON event_entities(entity_id)",
        "CREATE INDEX IF NOT EXISTS idx_ee_event        ON event_entities(event_id)",
        "CREATE INDEX IF NOT EXISTS idx_rel_a           ON relationships(entity_a)",
        "CREATE INDEX IF NOT EXISTS idx_rel_b           ON relationships(entity_b)",
    ]:
        conn.execute(ddl)

    logger.info("Schema ready.")
