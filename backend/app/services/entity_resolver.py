"""
Entity Resolver
Maps variant actor names to canonical entities.

Bug fixed from v1: GDELT Actor country codes (IND, CHN, USA…) were being
stored as entities. These are now filtered out — only proper names are resolved.

Resolution order:
  1. Skip bare country codes (3-letter CAMEO codes)
  2. Exact alias match
  3. Fuzzy match (SequenceMatcher > 0.85)
  4. Title-case passthrough
"""
import logging
import re
import uuid
from difflib import SequenceMatcher

from app.core.database import get_conn

logger = logging.getLogger(__name__)

# ── Alias map ─────────────────────────────────────────────────────────────────
# "raw lowercase" → "canonical name"
KNOWN_ALIASES: dict[str, str] = {
    # Indian politicians
    "modi":                    "Narendra Modi",
    "pm modi":                 "Narendra Modi",
    "narendra modi":           "Narendra Modi",
    "prime minister modi":     "Narendra Modi",
    "pm":                      "Narendra Modi",
    "rahul":                   "Rahul Gandhi",
    "rahul gandhi":            "Rahul Gandhi",
    "rg":                      "Rahul Gandhi",
    "mamata":                  "Mamata Banerjee",
    "didi":                    "Mamata Banerjee",
    "mamata banerjee":         "Mamata Banerjee",
    "kejriwal":                "Arvind Kejriwal",
    "arvind kejriwal":         "Arvind Kejriwal",
    "aap leader":              "Arvind Kejriwal",
    "sitharaman":              "Nirmala Sitharaman",
    "nirmala sitharaman":      "Nirmala Sitharaman",
    "finance minister":        "Nirmala Sitharaman",
    "jaishankar":              "S. Jaishankar",
    "s jaishankar":            "S. Jaishankar",
    "s. jaishankar":           "S. Jaishankar",
    "external affairs minister": "S. Jaishankar",
    "amit shah":               "Amit Shah",
    "home minister":           "Amit Shah",
    "yogi":                    "Yogi Adityanath",
    "yogi adityanath":         "Yogi Adityanath",
    "cm yogi":                 "Yogi Adityanath",
    "nitish":                  "Nitish Kumar",
    "nitish kumar":            "Nitish Kumar",
    "chandrababu":             "Chandrababu Naidu",
    "chandrababu naidu":       "Chandrababu Naidu",
    "naidu":                   "Chandrababu Naidu",
    "omar":                    "Omar Abdullah",
    "omar abdullah":           "Omar Abdullah",
    "priyanka":                "Priyanka Gandhi Vadra",
    "priyanka gandhi":         "Priyanka Gandhi Vadra",
    "smriti irani":            "Smriti Irani",
    "rajnath":                 "Rajnath Singh",
    "rajnath singh":           "Rajnath Singh",

    # Organizations
    "bjp":                       "BJP",
    "bharatiya janata party":    "BJP",
    "congress":                  "Congress",
    "indian national congress":  "Congress",
    "inc":                       "Congress",
    "congress party":            "Congress",
    "aam aadmi party":           "AAP",
    "aap":                       "AAP",
    "trinamool":                 "TMC",
    "trinamool congress":        "TMC",
    "tmc":                       "TMC",
    "india alliance":            "INDIA Alliance",
    "opposition alliance":       "INDIA Alliance",
    "i.n.d.i.a":                "INDIA Alliance",
    "nda":                       "NDA",
    "national democratic alliance": "NDA",
    "rss":                       "RSS",
    "rashtriya swayamsevak sangh": "RSS",
    "vhp":                       "Vishwa Hindu Parishad",
    "vishwa hindu parishad":     "Vishwa Hindu Parishad",
    "election commission":       "Election Commission of India",
    "eci":                       "Election Commission of India",
    "supreme court":             "Supreme Court of India",
    "rbi":                       "Reserve Bank of India",
    "reserve bank":              "Reserve Bank of India",
    "reserve bank of india":     "Reserve Bank of India",
    "sebi":                      "SEBI",
    "ndma":                      "NDMA",
    "imd":                       "India Meteorological Department",

    # Countries (full names only — 3-letter codes are filtered separately)
    "india":         "India",
    "china":         "China",
    "pakistan":      "Pakistan",
    "united states": "United States",
    "america":       "United States",
    "bangladesh":    "Bangladesh",
    "sri lanka":     "Sri Lanka",
    "nepal":         "Nepal",
    "myanmar":       "Myanmar",
}

# ── Entity type map ───────────────────────────────────────────────────────────
ENTITY_TYPES: dict[str, str] = {
    "Narendra Modi": "politician",      "Rahul Gandhi": "politician",
    "Mamata Banerjee": "politician",    "Arvind Kejriwal": "politician",
    "Nirmala Sitharaman": "politician", "S. Jaishankar": "politician",
    "Amit Shah": "politician",          "Yogi Adityanath": "politician",
    "Nitish Kumar": "politician",       "Chandrababu Naidu": "politician",
    "Omar Abdullah": "politician",      "Priyanka Gandhi Vadra": "politician",
    "Smriti Irani": "politician",       "Rajnath Singh": "politician",

    "BJP": "organization",              "Congress": "organization",
    "AAP": "organization",              "TMC": "organization",
    "INDIA Alliance": "organization",   "NDA": "organization",
    "RSS": "organization",              "Vishwa Hindu Parishad": "organization",

    "Election Commission of India": "institution",
    "Supreme Court of India": "institution",
    "Reserve Bank of India": "institution",
    "SEBI": "institution",
    "NDMA": "institution",
    "India Meteorological Department": "institution",

    "India": "country",    "China": "country",
    "Pakistan": "country", "United States": "country",
    "Bangladesh": "country","Sri Lanka": "country",
    "Nepal": "country",    "Myanmar": "country",
}

# 3-letter CAMEO country codes — skip these, they are not person/org entities
_CAMEO_CODES: set[str] = {
    "IND","CHN","PAK","USA","GBR","RUS","FRA","DEU","JPN","AUS",
    "BRA","CAN","ZAF","NGA","KEN","SAU","IRN","IRQ","SYR","AFG",
    "BGD","LKA","NPL","MMR","THA","IDN","MYS","SGP","PHL","KOR",
    "PRK","ISR","PSE","TUR","EGY","LBY","SDN","UKR","POL","SWE",
    "GOV","MIL","REB","OPP","PTY","CVL","NGO","INT","IGO","MED",
    "EDU","BUS","CRM","LAB",   # GDELT actor type codes also appear here
}


class EntityResolver:

    def is_junk(self, name: str) -> bool:
        """Return True for names that should never become entities."""
        if not name or len(name) < 2:
            return True
        # 3-letter CAMEO codes
        if name.upper() in _CAMEO_CODES:
            return True
        # Pure numbers
        if re.fullmatch(r"[\d\s\-\.]+", name):
            return True
        # Single letters
        if len(name.strip()) <= 1:
            return True
        return False

    def normalize_name(self, raw: str) -> str | None:
        """Map a raw GDELT actor name to a canonical entity name."""
        if not raw or not raw.strip():
            return None
        if self.is_junk(raw):
            return None

        cleaned = re.sub(r"\s+", " ", raw.strip().lower())

        # Direct alias match
        if cleaned in KNOWN_ALIASES:
            return KNOWN_ALIASES[cleaned]

        # Fuzzy substring match
        for alias, canonical in KNOWN_ALIASES.items():
            if len(alias) >= 4 and (alias in cleaned or cleaned in alias):
                if SequenceMatcher(None, alias, cleaned).ratio() > 0.85:
                    return canonical

        # Return title-cased original — new entity will be created
        title = raw.strip().title()
        # Still skip if it looks like a country code after title-casing
        if title.upper() in _CAMEO_CODES:
            return None
        return title

    def get_or_create_entity(self, canonical_name: str) -> str | None:
        """Return existing entity ID or insert a new one. Returns None on failure."""
        if not canonical_name:
            return None
        conn = get_conn()
        row = conn.execute(
            "SELECT id FROM entities WHERE canonical_name = ?", [canonical_name]
        ).fetchone()
        if row:
            return row[0]

        eid = str(uuid.uuid4())
        etype = ENTITY_TYPES.get(canonical_name, "unknown")
        try:
            conn.execute("""
                INSERT INTO entities (id, canonical_name, aliases, entity_type, frequency)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT (id) DO NOTHING
            """, [eid, canonical_name, [canonical_name], etype])
            return eid
        except Exception as e:
            logger.debug(f"Entity insert error for '{canonical_name}': {e}")
            return None

    async def resolve_from_db(self, date_str: str):
        """
        After ingestion: pull Actor1Name / Actor2Name from stored events,
        normalize them, and populate event_entities + entities tables.
        """
        conn = get_conn()
        date_filter = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        rows = conn.execute("""
            SELECT e.id,
                   COALESCE(e.country_a, ''), COALESCE(e.country_b, ''),
                   COALESCE(e.location, '')
            FROM events e
            WHERE e.date = CAST(? AS DATE)
        """, [date_filter]).fetchall()

        if not rows:
            logger.info(f"[{date_str}] No events found for entity resolution.")
            return

        resolved = 0
        for event_id, ca, cb, loc in rows:
            # We use Actor country codes to find associated named actors
            # The Actor names are in the raw GDELT file but we didn't store them —
            # for now resolve from known alias list keyed by country code context.
            # A future improvement is to store Actor1Name during ingestion.
            candidates = [n for n in [ca, cb] if n and n not in _CAMEO_CODES]
            for raw_name in candidates:
                canonical = self.normalize_name(raw_name)
                if not canonical:
                    continue
                eid = self.get_or_create_entity(canonical)
                if not eid:
                    continue
                try:
                    conn.execute("""
                        INSERT INTO event_entities (event_id, entity_id, role)
                        VALUES (?, ?, 'actor')
                        ON CONFLICT (event_id, entity_id, role) DO NOTHING
                    """, [event_id, eid])
                    conn.execute(
                        "UPDATE entities SET frequency = frequency + 1 WHERE id = ?",
                        [eid]
                    )
                    resolved += 1
                except Exception:
                    pass

        logger.info(f"[{date_str}] Entity resolution: {resolved} links for {len(rows)} events.")
