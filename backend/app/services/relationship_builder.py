"""
Relationship Builder — Weighted Signal System
Builds OBSERVABLE relationships between events and entities.

CRITICAL DESIGN PRINCIPLE:
  Every relationship is evidence-based. No causal inference is ever made.
  "Event A happened before Event B" is NEVER treated as causation.

═══════════════════════════════════════════════════════════════════════
WEIGHTED SCORING MODEL
═══════════════════════════════════════════════════════════════════════

Each signal has a maximum weight. Confidence = sum of earned weights,
normalised to [0.0, 1.0].

  Signal                  Max weight   Rationale
  ─────────────────────── ──────────   ─────────────────────────────────
  Exact same location     0.30         Strongest observable link
  Shared country actors   0.20         Same geopolitical context
  Same CAMEO category     0.20         Same type of event
  Temporal proximity      0.15         Nearby in time (≤3d > ≤7d > ≤14d)
  Mention volume signal   0.10         High-mention events are more salient
  Source overlap          0.05         Same source reported both events

  Max total               1.00

The decay functions for temporal proximity:
  ≤1 day  → full 0.15
  ≤3 days → 0.10
  ≤7 days → 0.05
  >7 days → 0.00  (no temporal signal beyond a week)

No signal alone can exceed 0.30.
A relationship is stored only if total confidence ≥ 0.25.
═══════════════════════════════════════════════════════════════════════
"""
import logging
import uuid
from datetime import date

from app.core.database import get_conn

logger = logging.getLogger(__name__)

# ── Weights ───────────────────────────────────────────────────────────────────
W_LOCATION  = 0.30
W_COUNTRY   = 0.20
W_CATEGORY  = 0.20
W_TEMPORAL  = 0.15   # max; decays with days_apart
W_MENTIONS  = 0.10
W_SOURCE    = 0.05

MIN_CONFIDENCE = 0.25   # relationships below this are not stored
MIN_EVIDENCE   = 2      # minimum co-occurrence count for entity relationships


def _temporal_weight(days_apart: int) -> float:
    if days_apart <= 1:   return W_TEMPORAL
    if days_apart <= 3:   return W_TEMPORAL * 0.67
    if days_apart <= 7:   return W_TEMPORAL * 0.33
    return 0.0


def _mention_weight(mentions_a: int, mentions_b: int) -> float:
    """Higher-mention events get a small salience bonus."""
    avg = (mentions_a + mentions_b) / 2
    if avg >= 500:   return W_MENTIONS
    if avg >= 100:   return W_MENTIONS * 0.6
    if avg >= 20:    return W_MENTIONS * 0.3
    return 0.0


class RelationshipBuilder:

    async def build_from_db(self, date_str: str):
        """
        Build weighted event-to-event relationships for all events on date_str.
        Also triggers entity co-occurrence relationship building.
        """
        conn = get_conn()
        date_filter = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        # Pull events on this date
        today_events = conn.execute("""
            SELECT id, date, category, country_a, country_b,
                   location, num_mentions, source_url
            FROM events
            WHERE date = CAST(? AS DATE)
        """, [date_filter]).fetchall()

        if not today_events:
            logger.info(f"[{date_str}] No events to build relationships for.")
            return

        logger.info(f"[{date_str}] Building relationships for {len(today_events)} events…")
        stored_count = 0

        for ev in today_events:
            ev_id, ev_date, ev_cat, ca, cb, ev_loc, ev_mentions, ev_url = ev

            # Find candidate events within 14-day window (both directions)
            candidates = conn.execute("""
                SELECT id, date, category, country_a, country_b,
                       location, num_mentions, source_url
                FROM events
                WHERE id != ?
                  AND date BETWEEN (CAST(? AS DATE) - INTERVAL '14 days')
                               AND (CAST(? AS DATE) + INTERVAL '14 days')
                ORDER BY ABS(DATEDIFF('day', date, CAST(? AS DATE)))
                LIMIT 100
            """, [ev_id, date_filter, date_filter, date_filter]).fetchall()

            for near in candidates:
                near_id, near_date, near_cat, nca, ncb, near_loc, near_mentions, near_url = near

                # ── Compute days_apart safely ─────────────────────────────
                try:
                    if isinstance(ev_date, date) and isinstance(near_date, date):
                        days_apart = abs((ev_date - near_date).days)
                    else:
                        from datetime import datetime
                        d1 = ev_date   if isinstance(ev_date,   date) else datetime.strptime(str(ev_date)[:10],   "%Y-%m-%d").date()
                        d2 = near_date if isinstance(near_date, date) else datetime.strptime(str(near_date)[:10], "%Y-%m-%d").date()
                        days_apart = abs((d1 - d2).days)
                except Exception:
                    days_apart = 99

                # ── Signal computation ────────────────────────────────────
                score        = 0.0
                signals      = []
                explanation  = []

                # 1. Same location (highest weight)
                loc_a = (ev_loc   or "").split(",")[0].strip().lower()
                loc_b = (near_loc or "").split(",")[0].strip().lower()
                if loc_a and loc_b and loc_a == loc_b:
                    score += W_LOCATION
                    signals.append("co_location")
                    explanation.append(
                        f"same location: {loc_a.title()} "
                        f"[+{W_LOCATION:.0%}]"
                    )

                # 2. Shared country actors
                ev_countries   = {c for c in [ca, cb]   if c and len(c) == 3}
                near_countries = {c for c in [nca, ncb] if c and len(c) == 3}
                shared_c = ev_countries & near_countries
                if shared_c:
                    score += W_COUNTRY
                    signals.append("co_mention")
                    explanation.append(
                        f"shared actor countries: {', '.join(sorted(shared_c))} "
                        f"[+{W_COUNTRY:.0%}]"
                    )

                # 3. Same CAMEO category
                if ev_cat and near_cat and ev_cat == near_cat:
                    score += W_CATEGORY
                    signals.append("co_topic")
                    explanation.append(
                        f"same event type: {ev_cat} "
                        f"[+{W_CATEGORY:.0%}]"
                    )

                # 4. Temporal proximity (decaying weight)
                tw = _temporal_weight(days_apart)
                if tw > 0:
                    score += tw
                    signals.append("temporal_proximity")
                    explanation.append(
                        f"{days_apart}d apart — temporal proximity only, "
                        f"NOT causality [+{tw:.0%}]"
                    )

                # 5. Mention volume salience bonus
                mw = _mention_weight(ev_mentions or 0, near_mentions or 0)
                if mw > 0:
                    score += mw
                    explanation.append(
                        f"high mention volume (avg {((ev_mentions or 0)+(near_mentions or 0))//2}) "
                        f"[+{mw:.0%}]"
                    )

                # 6. Same source domain (weak signal)
                if ev_url and near_url:
                    try:
                        from urllib.parse import urlparse
                        d_a = urlparse(ev_url).netloc
                        d_b = urlparse(near_url).netloc
                        if d_a and d_b and d_a == d_b:
                            score += W_SOURCE
                            explanation.append(
                                f"same source domain: {d_a} [+{W_SOURCE:.0%}]"
                            )
                    except Exception:
                        pass

                # Clamp to [0, 1]
                confidence = min(1.0, score)

                # Only store if meets minimum threshold
                if confidence < MIN_CONFIDENCE or not signals:
                    continue

                expl_text = (
                    f"Confidence {confidence:.0%} from {len(signals)} signal(s): "
                    + "; ".join(explanation)
                    + " | Time proximity ≠ causality."
                )

                # Ordered pair so (A,B) and (B,A) map to the same row
                pair_a = min(ev_id, near_id)
                pair_b = max(ev_id, near_id)

                try:
                    conn.execute("""
                        INSERT INTO event_relationships
                            (event_a, event_b, rel_type,
                             score_co_location, score_co_country, score_co_category,
                             score_temporal, score_mention_vol,
                             days_apart, confidence, explanation)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (event_a, event_b, rel_type) DO UPDATE SET
                            confidence  = GREATEST(event_relationships.confidence,
                                                   excluded.confidence),
                            explanation = excluded.explanation
                    """, [
                        pair_a, pair_b, signals[0],
                        W_LOCATION  if "co_location" in signals else 0.0,
                        W_COUNTRY   if "co_mention"  in signals else 0.0,
                        W_CATEGORY  if "co_topic"    in signals else 0.0,
                        _temporal_weight(days_apart),
                        mw,
                        days_apart, confidence, expl_text,
                    ])
                    stored_count += 1
                except Exception as e:
                    logger.debug(f"Event relationship insert error: {e}")

        logger.info(f"[{date_str}] Stored {stored_count} event relationships.")
        await self._build_entity_cooccurrence(date_filter)

    async def _build_entity_cooccurrence(self, date_filter: str):
        """
        Entity-level relationships: entities that appear in the same
        events on the same day get a weighted co-occurrence score.

        Weighting:
          co_count ≥ 10 → confidence 0.90
          co_count ≥ 5  → confidence 0.70
          co_count ≥ 2  → confidence 0.50
          co_count = 1  → confidence 0.35
        """
        conn = get_conn()

        pairs = conn.execute("""
            SELECT
                ee1.entity_id AS a,
                ee2.entity_id AS b,
                COUNT(*)      AS co_count,
                SUM(e.num_mentions) AS total_mentions
            FROM event_entities ee1
            JOIN event_entities ee2
              ON ee1.event_id = ee2.event_id
             AND ee1.entity_id < ee2.entity_id
            JOIN events e ON e.id = ee1.event_id
            WHERE e.date = CAST(? AS DATE)
            GROUP BY ee1.entity_id, ee2.entity_id
            HAVING COUNT(*) >= 1
        """, [date_filter]).fetchall()

        stored = 0
        for entity_a, entity_b, co_count, total_mentions in pairs:
            # Weighted confidence
            if co_count >= 10:  conf = 0.90
            elif co_count >= 5: conf = 0.70
            elif co_count >= 2: conf = 0.50
            else:               conf = 0.35

            # Mention volume bonus (up to +0.05)
            vol_bonus = min(0.05, (total_mentions or 0) / 10_000)
            conf = min(0.95, conf + vol_bonus)

            explanation = (
                f"Co-mentioned in {co_count} event record(s) on {date_filter}. "
                f"Total mention volume: {total_mentions or 0}. "
                f"Confidence {conf:.0%} based on co-occurrence frequency + volume. "
                f"This is a correlation signal — no causal or conspiratorial link is implied."
            )

            try:
                conn.execute("""
                    INSERT INTO relationships
                        (id, entity_a, entity_b, rel_type,
                         evidence_count, co_mention_count,
                         confidence, explanation,
                         first_seen, last_seen)
                    VALUES (?, ?, ?, 'co_mention', ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (entity_a, entity_b, rel_type) DO UPDATE SET
                        evidence_count   = relationships.evidence_count + excluded.evidence_count,
                        co_mention_count = relationships.co_mention_count + excluded.co_mention_count,
                        -- Recompute confidence as weighted average of old and new
                        confidence  = LEAST(0.95,
                                        (relationships.confidence * relationships.evidence_count
                                         + excluded.confidence * excluded.evidence_count)
                                        / (relationships.evidence_count + excluded.evidence_count)
                                      ),
                        last_seen   = excluded.last_seen,
                        explanation = excluded.explanation
                """, [
                    str(uuid.uuid4()),
                    entity_a, entity_b,
                    co_count, co_count,
                    conf, explanation,
                    date_filter, date_filter,
                ])
                stored += 1
            except Exception as e:
                logger.debug(f"Entity relationship insert error: {e}")

        logger.info(f"[{date_filter}] Stored {stored} entity co-occurrence relationships.")
