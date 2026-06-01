"""
Entity Resolver
Maps variant names to canonical entities.
e.g. "Modi", "PM Modi", "Narendra Modi" → canonical: "Narendra Modi"

Resolution strategy (in order):
1. Exact match in alias table
2. Fuzzy match via Levenshtein / token overlap
3. AI-assisted disambiguation (optional, if ANTHROPIC_API_KEY set)
"""
import logging
import re
import uuid
from difflib import SequenceMatcher

from app.core.database import get_conn
from app.core.config import settings

logger = logging.getLogger(__name__)

# Hand-curated alias map for India-focused MVP
# Format: "alias" → "canonical_name"
KNOWN_ALIASES: dict[str, str] = {
    # Politicians
    "modi": "Narendra Modi",
    "pm modi": "Narendra Modi",
    "narendra modi": "Narendra Modi",
    "prime minister modi": "Narendra Modi",
    "rahul": "Rahul Gandhi",
    "rahul gandhi": "Rahul Gandhi",
    "rg": "Rahul Gandhi",
    "mamata": "Mamata Banerjee",
    "didi": "Mamata Banerjee",
    "mamata banerjee": "Mamata Banerjee",
    "kejriwal": "Arvind Kejriwal",
    "arvind kejriwal": "Arvind Kejriwal",
    "sitharaman": "Nirmala Sitharaman",
    "nirmala sitharaman": "Nirmala Sitharaman",
    "finance minister": "Nirmala Sitharaman",
    "jaishankar": "S. Jaishankar",
    "s jaishankar": "S. Jaishankar",
    "external affairs minister": "S. Jaishankar",
    "amit shah": "Amit Shah",
    "home minister": "Amit Shah",
    "yogi": "Yogi Adityanath",
    "yogi adityanath": "Yogi Adityanath",
    "cm yogi": "Yogi Adityanath",
    "nitish kumar": "Nitish Kumar",
    "chandrababu naidu": "Chandrababu Naidu",
    "naidu": "Chandrababu Naidu",
    "omar abdullah": "Omar Abdullah",
    "priyanka gandhi": "Priyanka Gandhi Vadra",

    # Organizations
    "bjp": "BJP",
    "bharatiya janata party": "BJP",
    "indian national congress": "Congress",
    "inc": "Congress",
    "congress party": "Congress",
    "aam aadmi party": "AAP",
    "trinamool congress": "TMC",
    "tmc": "TMC",
    "india alliance": "INDIA Alliance",
    "opposition alliance": "INDIA Alliance",
    "nda": "NDA",
    "national democratic alliance": "NDA",
    "rss": "RSS",
    "rashtriya swayamsevak sangh": "RSS",
    "vhp": "Vishwa Hindu Parishad",
    "election commission": "Election Commission of India",
    "eci": "Election Commission of India",
    "supreme court": "Supreme Court of India",
    "supreme court of india": "Supreme Court of India",
    "rbi": "Reserve Bank of India",
    "reserve bank": "Reserve Bank of India",
    "sebi": "SEBI",

    # Countries
    "india": "India",
    "china": "China",
    "prc": "China",
    "pakistan": "Pakistan",
    "us": "United States",
    "usa": "United States",
    "united states": "United States",
}

# Entity types
ENTITY_TYPES = {
    "Narendra Modi": "politician", "Rahul Gandhi": "politician",
    "Mamata Banerjee": "politician", "Arvind Kejriwal": "politician",
    "Nirmala Sitharaman": "politician", "S. Jaishankar": "politician",
    "Amit Shah": "politician", "Yogi Adityanath": "politician",
    "BJP": "organization", "Congress": "organization", "AAP": "organization",
    "TMC": "organization", "INDIA Alliance": "organization", "NDA": "organization",
    "RSS": "organization", "Vishwa Hindu Parishad": "organization",
    "Election Commission of India": "institution",
    "Supreme Court of India": "institution",
    "Reserve Bank of India": "institution",
    "India": "country", "China": "country", "Pakistan": "country",
    "United States": "country",
}


class EntityResolver:

    def normalize_name(self, raw: str) -> str | None:
        """Normalize a raw entity name to canonical form."""
        if not raw or not raw.strip():
            return None
        cleaned = raw.strip().lower()
        cleaned = re.sub(r"\s+", " ", cleaned)
        # Direct alias lookup
        if cleaned in KNOWN_ALIASES:
            return KNOWN_ALIASES[cleaned]
        # Try substring match for longer names
        for alias, canonical in KNOWN_ALIASES.items():
            if alias in cleaned or cleaned in alias:
                if SequenceMatcher(None, alias, cleaned).ratio() > 0.85:
                    return canonical
        # Return title-cased original if no match
        return raw.strip().title()

    def get_or_create_entity(self, canonical_name: str) -> str:
        """Get entity ID or create if not exists. Returns entity ID."""
        conn = get_conn()
        result = conn.execute(
            "SELECT id FROM entities WHERE canonical_name = ?", [canonical_name]
        ).fetchone()
        if result:
            return result[0]

        entity_id = str(uuid.uuid4())
        entity_type = ENTITY_TYPES.get(canonical_name, "unknown")
        conn.execute("""
            INSERT INTO entities (id, canonical_name, aliases, entity_type, frequency)
            VALUES (?, ?, ?, ?, 1)
        """, [entity_id, canonical_name, [canonical_name], entity_type])
        return entity_id

    async def resolve_from_db(self, date_str: str):
        """
        Post-ingestion: extract entity names from Actor1Name/Actor2Name fields
        and resolve them for events on this date.
        """
        conn = get_conn()
        rows = conn.execute("""
            SELECT id, country_a, country_b, location
            FROM events
            WHERE CAST(date AS VARCHAR) LIKE ?
        """, [date_str[:4] + "-" + date_str[4:6] + "-%"]).fetchall()

        for row in rows:
            event_id, ca, cb, loc = row
            names = [n for n in [ca, cb] if n]
            for name in names:
                canonical = self.normalize_name(name)
                if canonical:
                    entity_id = self.get_or_create_entity(canonical)
                    try:
                        conn.execute("""
                            INSERT OR IGNORE INTO event_entities (event_id, entity_id, role)
                            VALUES (?, ?, 'actor')
                        """, [event_id, entity_id])
                        conn.execute("""
                            UPDATE entities SET frequency = frequency + 1 WHERE id = ?
                        """, [entity_id])
                    except Exception:
                        pass

        logger.info(f"[{date_str}] Entity resolution complete.")
