"""
Relationship Builder
Builds OBSERVABLE relationships between entities and events.

CRITICAL DESIGN PRINCIPLE:
  - All relationships must be evidenced by data signals
  - No causal inference: "A happened before B" ≠ "A caused B"
  - Every relationship includes: type, evidence_count, explanation
  - Confidence = evidence strength, NOT causal confidence

Allowed relationship types:
  co_mention        — entities appeared in same articles
  co_location       — events occurred in same location
  co_topic          — shared topic/theme tags
  temporal_proximity — events within N days (NOT causal)
  org_affiliation   — entity is member of organization (from known data)
  repeated_co_occurrence — pattern of co-occurrence over time
"""
import logging
import uuid
from datetime import timedelta

from app.core.database import get_conn

logger = logging.getLogger(__name__)

# Time window for "temporal proximity" (days)
TEMPORAL_WINDOW_DAYS = 7

# Minimum evidence for a relationship to be stored
MIN_EVIDENCE = 2


class RelationshipBuilder:

    async def build_from_db(self, date_str: str):
        """Build relationships for events ingested on this date."""
        conn = get_conn()

        # Get events from this date
        date_filter = date_str[:4] + "-" + date_str[4:6] + "-" + date_str[6:8]
        events = conn.execute("""
            SELECT id, date, category, country_a, country_b, location
            FROM events
            WHERE date = ?
        """, [date_filter]).fetchall()

        logger.info(f"[{date_str}] Building relationships for {len(events)} events...")

        for ev in events:
            event_id, ev_date, ev_cat, ca, cb, ev_loc = ev

            # Get nearby events (temporal window)
            nearby = conn.execute("""
                SELECT id, date, category, country_a, country_b, location
                FROM events
                WHERE id != ?
                  AND ABS(DATEDIFF('day', date, ?::DATE)) <= ?
                ORDER BY ABS(DATEDIFF('day', date, ?::DATE))
                LIMIT 50
            """, [event_id, date_filter, TEMPORAL_WINDOW_DAYS, date_filter]).fetchall()

            for near in nearby:
                near_id, near_date, near_cat, nca, ncb, near_loc = near

                # Compute relationship signals
                signals = []
                explanation_parts = []

                # Co-location signal
                if ev_loc and near_loc and ev_loc.strip() and near_loc.strip():
                    if ev_loc.split(",")[0].strip() == near_loc.split(",")[0].strip():
                        signals.append("co_location")
                        explanation_parts.append(f"same location: {ev_loc.split(',')[0].strip()}")

                # Country overlap
                ev_countries = {c for c in [ca, cb] if c}
                near_countries = {c for c in [nca, ncb] if c}
                shared_countries = ev_countries & near_countries
                if shared_countries:
                    signals.append("co_mention")
                    explanation_parts.append(f"shared countries: {', '.join(shared_countries)}")

                # Same category
                if ev_cat and ev_cat == near_cat:
                    signals.append("co_topic")
                    explanation_parts.append(f"same event category: {ev_cat}")

                # Temporal proximity (note: explicitly NOT causal)
                days_apart = abs((ev_date - near_date).days) if hasattr(ev_date, 'days') else 0
                if days_apart <= 3:
                    signals.append("temporal_proximity")
                    explanation_parts.append(
                        f"events {days_apart} days apart (temporal proximity only — "
                        f"no causal relationship implied)"
                    )

                if len(signals) >= 1:
                    confidence = min(0.95, 0.3 + len(signals) * 0.2)
                    explanation = "Connected because: " + "; ".join(explanation_parts)

                    try:
                        conn.execute("""
                            INSERT OR IGNORE INTO event_relationships
                            (event_a, event_b, rel_type, days_apart, confidence, explanation)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, [
                            min(event_id, near_id),
                            max(event_id, near_id),
                            signals[0],  # Primary relationship type
                            days_apart,
                            confidence,
                            explanation,
                        ])
                    except Exception:
                        pass

        # Build entity co-occurrence relationships
        await self._build_entity_cooccurrence(date_filter)
        logger.info(f"[{date_str}] Relationship building complete.")

    async def _build_entity_cooccurrence(self, date_filter: str):
        """
        Find entities that appear in articles on the same day.
        This is a co-mention signal — NOT an implied connection.
        """
        conn = get_conn()
        # Entities co-occurring in events on the same date
        rows = conn.execute("""
            SELECT ee1.entity_id, ee2.entity_id, COUNT(*) as co_count
            FROM event_entities ee1
            JOIN event_entities ee2 ON ee1.event_id = ee2.event_id AND ee1.entity_id < ee2.entity_id
            JOIN events e ON e.id = ee1.event_id
            WHERE e.date = ?
            GROUP BY ee1.entity_id, ee2.entity_id
            HAVING COUNT(*) >= ?
        """, [date_filter, MIN_EVIDENCE]).fetchall()

        for entity_a, entity_b, co_count in rows:
            confidence = min(0.9, 0.3 + co_count * 0.1)
            explanation = (
                f"Co-mentioned in {co_count} event records on {date_filter}. "
                f"This is a co-occurrence signal only. "
                f"No causal or conspiratorial relationship is implied."
            )
            try:
                conn.execute("""
                    INSERT INTO relationships
                    (id, entity_a, entity_b, rel_type, evidence_count, confidence,
                     explanation, first_seen, last_seen)
                    VALUES (?, ?, ?, 'co_mention', ?, ?, ?, ?, ?)
                    ON CONFLICT (entity_a, entity_b, rel_type) DO UPDATE SET
                      evidence_count = evidence_count + excluded.evidence_count,
                      confidence = LEAST(0.95, confidence + 0.02),
                      last_seen = excluded.last_seen
                """, [
                    str(uuid.uuid4()),
                    entity_a, entity_b,
                    co_count, confidence, explanation,
                    date_filter, date_filter,
                ])
            except Exception:
                pass
