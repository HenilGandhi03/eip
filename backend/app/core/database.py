"""
DuckDB database layer.
For production, swap to PostgreSQL with asyncpg.
Neo4j can be added for graph queries.
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
    logger.info("Initializing DuckDB schema...")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id            VARCHAR PRIMARY KEY,
            date          DATE NOT NULL,
            year          INTEGER,
            month         INTEGER,
            day           INTEGER,
            title         VARCHAR,
            summary       VARCHAR,
            category      VARCHAR,         -- CAMEO event code label
            cameo_code    VARCHAR,         -- Raw CAMEO code
            goldstein     DOUBLE,          -- Goldstein conflict scale (-10 to +10)
            tone          DOUBLE,          -- Article tone score
            country_a     VARCHAR,         -- Actor 1 country
            country_b     VARCHAR,         -- Actor 2 country
            location      VARCHAR,         -- Event location string
            lat           DOUBLE,
            lon           DOUBLE,
            num_mentions  INTEGER,
            num_sources   INTEGER,
            num_articles  INTEGER,
            source_url    VARCHAR,         -- Primary GDELT source URL
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id            VARCHAR PRIMARY KEY,
            canonical_name VARCHAR NOT NULL,  -- Normalized name
            aliases       VARCHAR[],           -- All seen forms
            entity_type   VARCHAR,            -- politician/organization/country/topic
            country       VARCHAR,
            frequency     INTEGER DEFAULT 0,
            first_seen    DATE,
            last_seen     DATE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_entities (
            event_id      VARCHAR REFERENCES events(id),
            entity_id     VARCHAR REFERENCES entities(id),
            role          VARCHAR,  -- actor1/actor2/location/theme
            PRIMARY KEY (event_id, entity_id, role)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS relationships (
            id            VARCHAR PRIMARY KEY,
            entity_a      VARCHAR REFERENCES entities(id),
            entity_b      VARCHAR REFERENCES entities(id),
            rel_type      VARCHAR NOT NULL,   -- co_mention/co_location/co_topic/org_affiliation
            evidence_count INTEGER DEFAULT 0,
            confidence    DOUBLE DEFAULT 0.0,
            explanation   VARCHAR,
            first_seen    DATE,
            last_seen     DATE,
            UNIQUE(entity_a, entity_b, rel_type)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_relationships (
            event_a       VARCHAR REFERENCES events(id),
            event_b       VARCHAR REFERENCES events(id),
            rel_type      VARCHAR NOT NULL,
            shared_entities VARCHAR[],
            shared_themes VARCHAR[],
            days_apart    INTEGER,
            confidence    DOUBLE,
            explanation   VARCHAR,
            PRIMARY KEY (event_a, event_b, rel_type)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS gkg_records (
            id            VARCHAR PRIMARY KEY,
            date          DATE,
            source_url    VARCHAR,
            themes        VARCHAR[],
            locations     VARCHAR[],
            persons       VARCHAR[],
            organizations VARCHAR[],
            tone          DOUBLE,
            positive_score DOUBLE,
            negative_score DOUBLE,
            polarity      DOUBLE,
            activity_density DOUBLE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_log (
            id            VARCHAR PRIMARY KEY,
            file_date     DATE,
            file_url      VARCHAR,
            status        VARCHAR,  -- pending/success/error
            records_processed INTEGER DEFAULT 0,
            error_msg     VARCHAR,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_date ON events(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_country ON events(country_a)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_category ON events(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_entities_entity ON event_entities(entity_id)")

    logger.info("Database schema initialized.")
